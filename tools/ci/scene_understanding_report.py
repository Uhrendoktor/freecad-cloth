# Copyright (C) 2026 FreeCAD Cloth contributors
"""Summarize cloth scene evidence into a compact, artifact-only diagnosis dossier.

This script runs on the GitHub Actions host after the FreeCAD process exits. It
reads only files produced by that workflow run and never queries a live GUI or
external service.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import html
import json
import math
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast


SCHEMA = "freecad-cloth.scene-understanding"
SCHEMA_VERSION = 1
TWO_DIMENSIONAL_COORDINATE_COUNT = 2
TOPOLOGY_BOUNDARY_SAMPLE_FIELD_COUNT = 6
NEAR_CROSSING_RECORD_FIELD_COUNT = 5
MINIMUM_PANEL_BOUND_COORDINATES = 6
MINIMUM_CURVE_SAMPLE_COUNT = 2
CROSSING_DISTANCE_TOLERANCE_MM = 1e-6
BOUNDARY_POINT_CLOSURE_TOLERANCE_MM = 1e-5

_TOPOLOGY_RE = re.compile(
    r"tunic-outline-topology piece=(\S+) ir-valid=(True|False) ir-reason=(.*?) "
    r"draft-valid=(True|False) draft-reason=(.*?) ir-points=(\d+) draft-points=(\d+) "
    r"boundary-order=(.*?) near-crossing=(.*)$"
)
_ARMHOLE_RE = re.compile(
    r"tunic-native-armhole index=(\d+) type=(\S+) range=(\([^)]*\)) "
    r"start=(\([^)]*\)) end=(\([^)]*\)) bounds=(\([^)]*\)) "
    r"inward-scoop=([-+0-9.eE]+) samples=(\(.*\))$"
)
_POSE_RE = re.compile(
    r"tunic-pose-geometry left_dx=([-+0-9.eE]+) left_dz=([-+0-9.eE]+) "
    r"right_dx=([-+0-9.eE]+) right_dz=([-+0-9.eE]+)"
)
_PLACEMENT_RE = re.compile(
    r"tunic-placement-depth side=(\S+) projected-target-y=\[([^,\]]+), ([^\]]+)\] "
    r"panel-y=([-+0-9.eE]+) clearance-mm=([-+0-9.eE]+) "
    r"torso-x=\[([^,\]]+), ([^\]]+)\] projected-vertices=(\d+)"
)
_SCREENSHOT_RE = re.compile(r"screenshot=(.*?) state=(.*?) bytes=(\d+)$")
_CROSSING_RE = re.compile(r"Self-intersection\[([-+0-9.eE]+)\s+([-+0-9.eE]+)\]")


@dataclass(slots=True)
class WorkflowAssessment:
    """Terminal workflow classification and authoritative pattern findings.

    Attributes:
        topology_records: All available topology records.
        invalid_native: Native outlines failing the authoritative topology check.
        invalid_derived: Derived outlines failing the downstream representation check.
        invalid_geometry: Deduplicated causal geometry failures for report output.
        failure_text: Concatenated failure lines, or None if no failures were logged.
        failure_unknown: Whether a failure was observed without a classified geometry cause.
        result: Overall workflow state before fit-review warnings are applied.
        failed_stage: Earliest known failed stage, or None when not classified as failed.
        last_completed_stage: Last stage supported by the progress markers.
        next_action: Guidance for the next diagnostic or repair step.
    """

    topology_records: list[dict[str, object]]
    invalid_native: list[dict[str, object]]
    invalid_derived: list[dict[str, object]]
    invalid_geometry: list[dict[str, object]]
    failure_text: str | None
    failure_unknown: bool
    result: str
    failed_stage: str | None
    last_completed_stage: str
    next_action: str


@dataclass(slots=True)
class ProgressEvidence:
    """Progress-log observations collected for a workflow scene report.

    Attributes:
        topology_by_piece: Parsed native/derived topology records keyed by piece.
        armholes_by_index: Armhole samples keyed by boundary edge index.
        placements_by_side: Measured target-relative placement keyed by side.
        pose: Reported mannequin pose measurement, when present.
        screenshot_states: Screenshots reported by the workflow progress log.
        drape_records: Decoded drape metrics records from log markers.
        failure_lines: Explicit failure markers captured from the progress log.
        has_scenario_pass: Whether a successful terminal marker was observed.
        has_simulation_start: Whether simulation startup was observed.
    """

    topology_by_piece: dict[str, dict[str, object]] = field(default_factory=dict)
    armholes_by_index: dict[int, dict[str, object]] = field(default_factory=dict)
    placements_by_side: dict[str, dict[str, object]] = field(default_factory=dict)
    pose: dict[str, float] | None = None
    screenshot_states: dict[str, dict[str, object]] = field(default_factory=dict)
    drape_records: list[dict[str, object]] = field(default_factory=list)
    failure_lines: list[str] = field(default_factory=list)
    has_scenario_pass: bool = False
    has_simulation_start: bool = False


@dataclass(frozen=True, slots=True)
class _ScreenshotPresence:
    """Record the expected scene screenshots found in the completed run.

    Attributes:
        avatar: Whether the mannequin pose screenshot is available.
        pattern: Whether the pattern-design screenshot is available.
        sewing: Whether the sewing-preview screenshot is available.
        drape: Whether any post-drape screenshot is available.
    """

    avatar: bool
    pattern: bool
    sewing: bool
    drape: bool


def _literal_tuple(value: str) -> tuple[object, ...]:
    """Safely parse a tuple-like value written by Python's diagnostic repr.

    Args:
        value: Text containing a Python tuple representation.

    Returns:
        Parsed tuple with its original element values.

    Raises:
        TypeError: If the parsed diagnostic value is not a tuple.
    """
    parsed = ast.literal_eval(value)
    if not isinstance(parsed, tuple):
        msg = "expected a tuple in the workflow diagnostic"
        raise TypeError(msg)
    return cast("tuple[object, ...]", parsed)


def _point(value: object) -> list[float]:
    """Normalize a 2D point to a JSON-safe list of finite floats.

    Args:
        value: Candidate point value containing at least two coordinates.

    Returns:
        Two finite floating-point coordinates suitable for JSON output.

    Raises:
        ValueError: Raised when the point shape or coordinates are invalid.
    """
    if not isinstance(value, (tuple, list)) or len(value) < TWO_DIMENSIONAL_COORDINATE_COUNT:
        msg = "invalid 2D point in topology diagnostics"
        raise ValueError(msg)
    result = [float(value[0]), float(value[1])]
    if not all(math.isfinite(item) for item in result):
        msg = "non-finite point in topology diagnostics"
        raise ValueError(msg)
    return result


def _pair(value: str) -> list[float]:
    """Parse a point or bounding interval encoded using Python tuple syntax.

    Args:
        value: Tuple-like text describing a point or interval.

    Returns:
        Coordinate values parsed as floating-point numbers.
    """
    return _point(_literal_tuple(value))


def _parse_topology(line: str) -> dict[str, object] | None:
    """Extract the authoritative sampled boundary and nearest crossing segments.

    Args:
        line: Diagnostic line emitted by the native topology audit.

    Returns:
        Parsed topology details, or None when the line has no topology record.
    """
    match = _TOPOLOGY_RE.search(line)
    if match is None:
        return None
    raw_boundaries = _literal_tuple(match.group(8))
    boundaries: list[dict[str, object]] = []
    for item in raw_boundaries:
        if not isinstance(item, tuple) or len(item) not in {5, 6}:
            continue
        edge_name = str(item[0])
        edge_match = re.search(r":edge:(\d+)$", edge_name)
        boundary: dict[str, object] = {
            "id": edge_name,
            "edge_index": int(edge_match.group(1)) if edge_match else None,
            "kind": str(item[1]),
            "sample_count": int(item[2]),
            "start_mm": _point(item[3]),
            "end_mm": _point(item[4]),
        }
        if len(item) == TOPOLOGY_BOUNDARY_SAMPLE_FIELD_COUNT and isinstance(item[5], tuple):
            boundary["samples_local_mm"] = [_point(point) for point in item[5]]
        boundaries.append(boundary)
    raw_nearby = _literal_tuple(match.group(9))
    nearby: list[dict[str, object]] = []
    for item in raw_nearby:
        if not isinstance(item, tuple) or len(item) != NEAR_CROSSING_RECORD_FIELD_COUNT:
            continue
        nearby.append(
            {
                "distance_mm": float(item[0]),
                "sample_segment_index": int(item[1]),
                "edge_id": str(item[2]),
                "start_mm": _point(item[3]),
                "end_mm": _point(item[4]),
            }
        )
    ir_reason = match.group(3)
    draft_reason = match.group(5)
    crossing_match = _CROSSING_RE.search(ir_reason) or _CROSSING_RE.search(draft_reason)
    crossing = (
        [float(crossing_match.group(1)), float(crossing_match.group(2))] if crossing_match else None
    )
    return {
        "piece": match.group(1),
        "ir_valid": match.group(2) == "True",
        "ir_reason": ir_reason,
        "draft_valid": match.group(4) == "True",
        "draft_reason": draft_reason,
        "ir_point_count": int(match.group(6)),
        "draft_point_count": int(match.group(7)),
        "boundary_order": boundaries,
        "near_crossing": nearby,
        "crossing_local_mm": crossing,
    }


def _parse_armhole(line: str) -> dict[str, object] | None:
    """Extract the native curve class, parameter interval, and sampled local shape.

    Args:
        line: Diagnostic line containing native armhole measurements.

    Returns:
        Parsed armhole metadata, or None when the line has no armhole record.
    """
    match = _ARMHOLE_RE.search(line)
    if match is None:
        return None
    samples = _literal_tuple(match.group(8))
    return {
        "edge_index": int(match.group(1)),
        "curve_type": match.group(2),
        "parameter_range": [float(value) for value in _literal_tuple(match.group(3))],
        "start_local_mm": _pair(match.group(4)),
        "end_local_mm": _pair(match.group(5)),
        "bounds_local_mm": [float(value) for value in _literal_tuple(match.group(6))],
        "inward_scoop_mm": float(match.group(7)),
        "samples_local_mm": [_point(value) for value in samples],
    }


def _image_inventory(output_root: Path, workspace: Path) -> list[dict[str, object]]:
    """Hash rendered evidence already emitted by the run; never modify source images.

    Args:
        output_root: Directory containing rendered images from the run.
        workspace: Root directory used to produce the evidence artifacts.

    Returns:
        Image inventory records with relative paths, sizes, and SHA-256 digests.
    """
    records: list[dict[str, object]] = []
    for path in sorted(output_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        try:
            relative = path.resolve().relative_to(workspace.resolve()).as_posix()
        except ValueError:
            relative = path.name
        records.append(
            {
                "path": relative,
                "role": "visual",
                "size_bytes": path.stat().st_size,
                "sha256": digest,
            }
        )
    return records


def _finite_metric_number(value: object) -> float | None:
    """Convert a valid numeric metric to a finite float, excluding booleans.

    Args:
        value: Candidate scalar extracted from the drape metrics payload.

    Returns:
        Finite floating-point value, or None for unsupported/non-finite values.
    """
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _panel_vertical_bounds(
    panels: list[object],
) -> tuple[list[float], list[float], set[str]]:
    """Collect finite panel Z bounds and named diagnostic flags.

    Args:
        panels: Panel entries from a previously decoded drape metrics payload.

    Returns:
        Minimum and maximum Z coordinates per panel plus observed diagnostic names.
    """
    minimum_z: list[float] = []
    maximum_z: list[float] = []
    diagnostic_names: set[str] = set()
    for raw_panel in panels:
        if not isinstance(raw_panel, dict):
            continue
        bounds = raw_panel.get("bounds")
        if isinstance(bounds, list) and len(bounds) >= MINIMUM_PANEL_BOUND_COORDINATES:
            low = _finite_metric_number(bounds[4])
            high = _finite_metric_number(bounds[5])
            if low is not None and high is not None and low <= high:
                minimum_z.append(low)
                maximum_z.append(high)
        diagnostics = raw_panel.get("diagnostics")
        if isinstance(diagnostics, list):
            diagnostic_names.update(str(item) for item in diagnostics)
    return minimum_z, maximum_z, diagnostic_names


def _fit_findings(
    deviations: dict[str, float], review_threshold_mm: float
) -> list[dict[str, object]]:
    """Build review warnings for vertical deviations beyond the existing threshold.

    Args:
        deviations: Observed non-negative fit deviations keyed by report schema.
        review_threshold_mm: Existing heuristic review threshold in millimetres.

    Returns:
        Ordered warning records for deviations above the heuristic threshold.
    """
    finding_specs = (
        (
            "cloth_top_below_shoulder_reference",
            "cloth_top_below_shoulder_reference",
            "highest final cloth point is materially below the estimated shoulder reference",
        ),
        (
            "cloth_top_above_shoulder_reference",
            "cloth_top_above_shoulder_reference",
            "highest final cloth point is materially above the estimated shoulder reference",
        ),
        (
            "cloth_extends_below_expected_hem",
            "cloth_extends_below_expected_hem",
            "lowest final cloth point extends materially below the declared hem level",
        ),
        (
            "cloth_ends_above_expected_hem",
            "cloth_ends_above_expected_hem",
            "lowest final cloth point ends materially above the declared hem level",
        ),
    )
    findings: list[dict[str, object]] = []
    for kind, deviation_key, message in finding_specs:
        observed_mm = deviations[deviation_key]
        if observed_mm > review_threshold_mm:
            findings.append(
                {
                    "kind": kind,
                    "severity": "warning",
                    "observed_mm": round(observed_mm, 3),
                    "review_threshold_mm": round(review_threshold_mm, 3),
                    "message": message,
                }
            )
    return findings


def _fit_assessment(metrics_payload: object) -> dict[str, object]:
    """Screen garment vertical coverage separately from execution/contact success.

    The shoulder reference currently comes from the audit's avatar-bounds heuristic,
    not an authoritative anatomical landmark. Findings are therefore warnings for
    review, never a proof of fit failure or a reason to tune the solver.

    Args:
        metrics_payload: Decoded visual metrics emitted by the drape audit.

    Returns:
        Assessment state, measurement summary, and any garment-coverage findings.
    """
    if not isinstance(metrics_payload, dict):
        return {
            "state": "not_assessed",
            "reason": "drape-visual-metrics.json is absent or unavailable",
            "findings": [],
        }
    panels = metrics_payload.get("panels")
    if not isinstance(panels, list):
        return {
            "state": "not_assessed",
            "reason": "drape metrics do not contain a panel list",
            "findings": [],
        }
    hem_z = _finite_metric_number(metrics_payload.get("hem_z"))
    shoulder_z = _finite_metric_number(metrics_payload.get("shoulder_z"))
    target_height = _finite_metric_number(metrics_payload.get("target_height"))
    if hem_z is None or shoulder_z is None or target_height is None or target_height <= 0:
        return {
            "state": "not_assessed",
            "reason": "required hem, shoulder-reference, or target-height measurement is missing",
            "findings": [],
        }
    minimum_z, maximum_z, diagnostic_names = _panel_vertical_bounds(panels)
    if not minimum_z or not maximum_z:
        return {
            "state": "not_assessed",
            "reason": "no finite final panel Z bounds were available",
            "findings": [],
        }

    observed_min_z = min(minimum_z)
    observed_max_z = max(maximum_z)
    # Five percent of avatar height is a review trigger, not an acceptance
    # threshold. A named anatomical landmark should replace this proxy later.
    review_threshold_mm = max(50.0, 0.05 * target_height)
    deviations = {
        "cloth_top_below_shoulder_reference": max(0.0, shoulder_z - observed_max_z),
        "cloth_top_above_shoulder_reference": max(0.0, observed_max_z - shoulder_z),
        "cloth_extends_below_expected_hem": max(0.0, hem_z - observed_min_z),
        "cloth_ends_above_expected_hem": max(0.0, observed_min_z - hem_z),
    }
    findings = _fit_findings(deviations, review_threshold_mm)
    state = (
        "review_required"
        if findings or "below-hem-candidate" in diagnostic_names
        else "within_heuristic_tolerance"
    )
    if state == "review_required":
        next_action = (
            "Inspect front/rear/left/right views and verify the garment top, hem, named body "
            "landmarks, and required attachment constraints. Keep geometry/contact thresholds "
            "unchanged."
        )
    else:
        next_action = (
            "This bounds screen found no large vertical deviation, but does not certify "
            "coverage, fit, or attachment; inspect the multi-view screenshots and named "
            "landmarks."
        )
    return {
        "state": state,
        "method": (
            "final panel world-space Z bounds compared with declared hem and "
            "bounding-box-derived shoulder reference"
        ),
        "reference_levels_mm": {
            "hem_z": hem_z,
            "shoulder_z": shoulder_z,
            "shoulder_reference_source": (
                "avatar bounding-box heuristic, not an anatomical landmark"
            ),
        },
        "observed_final_panel_z_mm": {
            "minimum": round(observed_min_z, 3),
            "maximum": round(observed_max_z, 3),
        },
        "deviations_mm": {key: round(value, 3) for key, value in deviations.items()},
        "review_threshold_mm": round(review_threshold_mm, 3),
        "findings": findings,
        "other_diagnostics": sorted(diagnostic_names),
        "interpretation_limit": (
            "A bounds mismatch is a fit-review signal, not a definitive garment-fit verdict. "
            "Non-penetration and seam coherence do not establish body coverage or attachment."
        ),
        "next_action": next_action,
    }


def _record_pose(line: str, parsed: ProgressEvidence) -> None:
    """Record mannequin pose measurements when the line contains a pose marker.

    Args:
        line: Progress-log line being parsed.
        parsed: Evidence record that receives the measured pose values.
    """
    match = _POSE_RE.search(line)
    if match is None:
        return
    parsed.pose = {
        "left_shoulder_wrist_dx_mm": float(match.group(1)),
        "left_shoulder_wrist_dz_mm": float(match.group(2)),
        "right_shoulder_wrist_dx_mm": float(match.group(3)),
        "right_shoulder_wrist_dz_mm": float(match.group(4)),
    }


def _record_placement(line: str, parsed: ProgressEvidence) -> None:
    """Record target-relative placement values when the line contains a marker.

    Args:
        line: Progress-log line being parsed.
        parsed: Evidence record that receives the measured placement values.
    """
    match = _PLACEMENT_RE.search(line)
    if match is None:
        return
    parsed.placements_by_side[match.group(1)] = {
        "projected_target_y_range_mm": [
            float(match.group(2)),
            float(match.group(3)),
        ],
        "panel_origin_y_mm": float(match.group(4)),
        "configured_clearance_mm": float(match.group(5)),
        "torso_x_range_mm": [
            float(match.group(6)),
            float(match.group(7)),
        ],
        "projected_target_vertex_count": int(match.group(8)),
    }


def _parse_progress_text(progress_text: str) -> ProgressEvidence:
    """Parse scene markers emitted by the FreeCAD workflow into typed records.

    Args:
        progress_text: Complete captured progress log from the workflow process.

    Returns:
        Parsed topology, placement, pose, screenshot, and simulation observations.
    """
    parsed = ProgressEvidence(has_simulation_start="tunic-simulation-start" in progress_text)
    for line in progress_text.splitlines():
        topology = _parse_topology(line)
        if topology is not None:
            parsed.topology_by_piece[str(topology["piece"])] = topology
        armhole = _parse_armhole(line)
        if armhole is not None:
            parsed.armholes_by_index[int(armhole["edge_index"])] = armhole
        _record_pose(line, parsed)
        _record_placement(line, parsed)
        screenshot = _SCREENSHOT_RE.search(line)
        if screenshot:
            raw_path = screenshot.group(1).strip()
            image_name = Path(raw_path.replace("/workspace/", "")).name
            parsed.screenshot_states[image_name] = {
                "reported_path": raw_path,
                "state": screenshot.group(2),
                "reported_size_bytes": int(screenshot.group(3)),
            }
        if line.startswith("drape-metrics="):
            try:
                parsed_metrics = json.loads(line.removeprefix("drape-metrics="))
            except json.JSONDecodeError:
                parsed_metrics = None
            if isinstance(parsed_metrics, dict):
                parsed.drape_records.append(cast("dict[str, object]", parsed_metrics))
        if "scenario-pass" in line or "tunic-audit-process-exit=success" in line:
            parsed.has_scenario_pass = True
        if "scenario-fail" in line or line.startswith("SCENARIO FAILURE:"):
            parsed.failure_lines.append(line.strip())

    return parsed


def _classify_workflow_progress(parsed: ProgressEvidence) -> WorkflowAssessment:
    """Classify terminal state from topology and progress markers without changing thresholds.

    Args:
        parsed: Observations decoded from the captured workflow progress log.

    Returns:
        Authoritative terminal state, stage boundary, and blocking topology findings.
    """
    topology_records = list(parsed.topology_by_piece.values())
    invalid_native = [record for record in topology_records if not bool(record["ir_valid"])]
    invalid_derived = [record for record in topology_records if not bool(record["draft_valid"])]
    invalid_geometry_by_piece = {str(record["piece"]): record for record in invalid_derived}
    # Preserve the earliest causal failure if native and derived outlines are both invalid.
    invalid_geometry_by_piece.update({str(record["piece"]): record for record in invalid_native})
    invalid_geometry = list(invalid_geometry_by_piece.values())
    failure_text = "\n".join(parsed.failure_lines)
    failure_unknown = bool(parsed.failure_lines) and not invalid_geometry
    if invalid_native:
        result = "blocked"
        failed_stage = "pattern_topology"
        last_completed_stage = "pattern_geometry_created"
        next_action = (
            "Repair the authoritative native PatternIR boundary so it is a simple polygon. "
            "Inspect the two reported crossing edges and local intersection coordinate. "
            "Do not change placement or solver settings."
        )
    elif invalid_derived:
        result = "blocked"
        failed_stage = "pattern_representation"
        last_completed_stage = "native_pattern_topology_validated"
        next_action = (
            "Repair the derived DraftingBoundary representation or its curve sampling. "
            "The native PatternIR passed its validity check, so do not alter garment placement "
            "or solver settings to compensate for a downstream representation mismatch."
        )
    elif parsed.has_scenario_pass and not parsed.failure_lines:
        result = "passed"
        failed_stage = None
        last_completed_stage = "drape" if parsed.drape_records else "simulation"
        next_action = (
            "Review final multi-view fit and keep the same strict geometry and collision gates."
        )
    elif parsed.failure_lines:
        result = "failed"
        failed_stage = (
            "unknown_from_available_markers" if failure_unknown else "simulation_or_later"
        )
        last_completed_stage = (
            "simulation_started" if parsed.has_simulation_start else "last_observed_stage"
        )
        next_action = (
            "Use the failure log and the last completed stage to localize the first failing "
            "invariant before changing any parameter."
        )
    else:
        result = "incomplete"
        failed_stage = None
        last_completed_stage = "unknown"
        next_action = (
            "Inspect available workflow output; the progress log did not record a terminal stage."
        )

    return WorkflowAssessment(
        topology_records=topology_records,
        invalid_native=invalid_native,
        invalid_derived=invalid_derived,
        invalid_geometry=invalid_geometry,
        failure_text=failure_text or None,
        failure_unknown=failure_unknown,
        result=result,
        failed_stage=failed_stage,
        last_completed_stage=last_completed_stage,
        next_action=next_action,
    )


def _derive_stage_states(
    parsed: ProgressEvidence,
    assessment: WorkflowAssessment,
    screenshots: _ScreenshotPresence,
) -> dict[str, str]:
    """Derive visible workflow stage states from validated observations and screenshots.

    Args:
        parsed: Parsed progress markers and captured measurements.
        assessment: Terminal workflow and topology classification.
        screenshots: Presence of the expected mannequin, pattern, sewing and drape images.

    Returns:
        State labels for all report stages and mannequin-pose capture.
    """
    if parsed.pose is not None and screenshots.avatar:
        pose_state = "passed"
    elif parsed.pose is not None:
        pose_state = "measured_but_image_not_found"
    else:
        pose_state = "not_observed"
    pattern_state = (
        "invalid"
        if assessment.invalid_native
        else (
            "valid"
            if assessment.topology_records
            and all(bool(item["ir_valid"]) for item in assessment.topology_records)
            else "not_observed"
        )
    )
    derived_state = (
        "invalid"
        if assessment.invalid_derived
        else (
            "valid"
            if assessment.topology_records
            and all(bool(item["draft_valid"]) for item in assessment.topology_records)
            else "not_observed"
        )
    )
    sewing_state = (
        "generated_from_invalid_pattern"
        if assessment.invalid_geometry and screenshots.sewing
        else "generated"
        if screenshots.sewing
        else "not_reached_or_not_captured"
    )
    if assessment.invalid_geometry:
        simulation_state = (
            "not_reached" if not parsed.has_simulation_start else "started_despite_invalid_pattern"
        )
    elif parsed.has_simulation_start:
        simulation_state = "started"
    else:
        simulation_state = "not_observed"
    if assessment.invalid_geometry and not parsed.has_simulation_start:
        drape_state = "not_reached"
    elif parsed.drape_records or screenshots.drape:
        drape_state = "evidence_present"
    elif not parsed.has_simulation_start:
        drape_state = "not_reached_or_not_captured"
    else:
        drape_state = "started_but_final_evidence_missing"

    return {
        "mannequin_pose": pose_state,
        "pattern_construction": (
            "captured"
            if assessment.topology_records or screenshots.pattern
            else "not_observed"
        ),
        "pattern_topology": pattern_state,
        "derived_pattern_representation": derived_state,
        "sewing_preview": sewing_state,
        "initial_placement": "measured" if parsed.placements_by_side else "not_observed",
        "simulation": simulation_state,
        "drape": drape_state,
    }


def _build_issues(
    invalid_geometry: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Describe invalid pattern topology while preserving source and measured edge evidence.

    Args:
        invalid_geometry: Native or derived outline records classified as invalid.

    Returns:
        Blocking pattern findings in report-schema form.
    """
    issues: list[dict[str, object]] = []
    for topology in invalid_geometry:
        native_invalid = not bool(topology["ir_valid"])
        reason = str(topology["ir_reason"] if native_invalid else topology["draft_reason"])
        nearby = cast("list[dict[str, object]]", topology["near_crossing"])
        touching = list(
            dict.fromkeys(
                str(item["edge_id"])
                for item in nearby
                if float(item["distance_mm"]) <= CROSSING_DISTANCE_TOLERANCE_MM
            )
        )
        issues.append(
            {
                "kind": (
                    "self_intersection"
                    if native_invalid and "Self-intersection" in reason
                    else "invalid_native_pattern"
                    if native_invalid
                    else "invalid_derived_outline"
                ),
                "severity": "blocker",
                "piece": topology["piece"],
                "reason": reason,
                "edge_ids": touching,
                "point_local_mm": topology["crossing_local_mm"],
                "source": (
                    "PatternIR sampled native boundary"
                    if native_invalid
                    else "derived DraftingBoundary representation"
                ),
                "effect": (
                    "native pattern, seam preview, and fitting are not valid evidence"
                    if native_invalid
                    else (
                        "the rendered/derived pattern boundary is not trustworthy even though "
                        "native PatternIR is valid"
                    )
                ),
            }
        )

    return issues


def _crossing_summary(
    invalid_geometry: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Summarize each observed crossing with local point and touching edge identifiers.

    Args:
        invalid_geometry: Invalid pattern outlines with validated nearby-crossing records.

    Returns:
        JSON-safe crossing summaries, excluding invalid outlines without a measured point.
    """
    return [
        {
            "piece": record["piece"],
            "point_local_mm": record["crossing_local_mm"],
            "edge_ids": [
                item["edge_id"]
                for item in cast("list[dict[str, object]]", record["near_crossing"])
                if float(item["distance_mm"]) <= CROSSING_DISTANCE_TOLERANCE_MM
            ],
        }
        for record in invalid_geometry
        if record["crossing_local_mm"] is not None
    ]


def build_report(progress_path: Path, output_root: Path, workspace: Path) -> dict[str, object]:
    """Build a machine-readable diagnosis using only the completed workflow files.

    Args:
        progress_path: Path to the captured workflow progress log.
        output_root: Directory used to locate the run's diagnostic evidence.
        workspace: Root path used to make evidence paths relative.

    Returns:
        Structured report describing workflow status and gathered evidence.
    """
    progress_text = (
        progress_path.read_text(encoding="utf-8", errors="replace")
        if progress_path.is_file()
        else ""
    )
    parsed = _parse_progress_text(progress_text)
    assessment = _classify_workflow_progress(parsed)
    screenshots = _ScreenshotPresence(
        avatar=(
            "cloth-mannequin-near-t-pose.png" in parsed.screenshot_states
            and (output_root / "cloth-mannequin-near-t-pose.png").is_file()
        ),
        pattern=(
            "cloth-pattern-design.png" in parsed.screenshot_states
            and (output_root / "cloth-pattern-design.png").is_file()
        ),
        sewing=(
            "cloth-sewing.png" in parsed.screenshot_states
            and (output_root / "cloth-sewing.png").is_file()
        ),
        drape=any(
            name.startswith("cloth-simulation-draped") for name in parsed.screenshot_states
        ),
    )
    stage_states = _derive_stage_states(parsed, assessment, screenshots)
    issues = _build_issues(assessment.invalid_geometry)
    image_inventory = _image_inventory(output_root, workspace)
    metrics_path = output_root / "drape-visual-metrics.json"
    metrics_payload: object = None
    if metrics_path.is_file():
        try:
            metrics_payload = json.loads(metrics_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            metrics_payload = {"parse_error": "drape-visual-metrics.json is not valid JSON"}
    result = assessment.result
    next_action = assessment.next_action
    fit_assessment = _fit_assessment(metrics_payload)
    # A successful FreeCAD script is execution evidence, not proof of fit. Keep
    # the execution stages intact while surfacing a separate fit-review outcome.
    if result == "passed" and fit_assessment.get("state") == "review_required":
        result = "review_required"
        next_action = str(fit_assessment.get("next_action", next_action))

    crossings = _crossing_summary(assessment.invalid_geometry)

    return {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "provenance": {
            "repository": os.environ.get("GITHUB_REPOSITORY"),
            "commit_sha": os.environ.get("OBSERVATION_COMMIT_SHA") or os.environ.get("GITHUB_SHA"),
            "workflow": os.environ.get("GITHUB_WORKFLOW"),
            "job": os.environ.get("GITHUB_JOB"),
            "event_name": os.environ.get("GITHUB_EVENT_NAME"),
            "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
            "workflow_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "test_script": os.environ.get("OBSERVATION_TEST_SCRIPT"),
            "container_image": os.environ.get("OBSERVATION_IMAGE"),
            "artifact_name": "tunic-visual-audit",
        },
        "status": {
            "result": result,
            "failed_stage": assessment.failed_stage,
            "last_completed_stage": assessment.last_completed_stage,
            "failure_text": assessment.failure_text,
        },
        "units": {
            "length": "mm",
            "pattern_coordinates": "piece-local 2D",
            "pose_and_placement_coordinates": (
                "FreeCAD world coordinates when specified by the producer"
            ),
        },
        "stages": stage_states,
        "mannequin_pose_measurements": parsed.pose,
        "pattern": {
            "pieces": assessment.topology_records,
            "native_armholes": [
                parsed.armholes_by_index[key] for key in sorted(parsed.armholes_by_index)
            ],
            "crossings": crossings,
        },
        "placement": {
            "panels": parsed.placements_by_side,
            "initial_target_clearance_log_lines": [
                line.strip()
                for line in progress_text.splitlines()
                if "step0-target-vertex-clearance-mm=" in line
            ],
        },
        "simulation": {
            "started": parsed.has_simulation_start,
            "drape_metrics_from_log": parsed.drape_records,
            "drape_metrics_json": metrics_payload,
        },
        "fit_assessment": fit_assessment,
        "issues": issues,
        "next_action": next_action,
        "evidence": {
            "images": image_inventory,
            "screenshot_log_entries": parsed.screenshot_states,
            "expected_or_known_outputs": {
                "mannequin_pose": "present" if screenshots.avatar else "missing",
                "pattern_design": "present" if screenshots.pattern else "missing",
                "sewing_preview": "present" if screenshots.sewing else "missing",
                "post_drape_views": "present" if screenshots.drape else "missing",
                "drape_metrics": "present" if metrics_path.is_file() else "missing",
            },
        },
        "report_files": {
            "summary_json": "scene-understanding.json",
            "summary_markdown": "scene-understanding.md",
            "annotated_pattern_svg": "scene-understanding.svg",
        },
    }


def _as_dict(value: object) -> dict[str, object]:
    """Return a dict for a previously validated report section.

    Args:
        value: Candidate value from a report section.

    Returns:
        Dictionary representation, or an empty mapping for non-dictionaries.
    """
    return cast("dict[str, object]", value) if isinstance(value, dict) else {}


def _as_list(value: object) -> list[object]:
    """Return a list for a previously validated report section.

    Args:
        value: Candidate value from a report section.

    Returns:
        List representation, or an empty list for non-lists.
    """
    return cast("list[object]", value) if isinstance(value, list) else []


def _boundary_edge_shape(
    boundary: dict[str, object],
    armholes: dict[int, dict[str, object]],
) -> tuple[int | None, list[list[float]], str]:
    """Resolve the sample points and label for a native pattern boundary.

    Args:
        boundary: One ordered boundary record from the scene report.
        armholes: Armhole samples indexed by native boundary edge index.

    Returns:
        Edge index, local points used for drawing, and the stable edge identifier.
    """
    edge_index_value = boundary.get("edge_index")
    edge_index = int(edge_index_value) if isinstance(edge_index_value, int) else None
    start = _point(boundary.get("start_mm"))
    end = _point(boundary.get("end_mm"))
    local_points = [start, end]
    sampled_boundary = cast("list[list[float]]", boundary.get("samples_local_mm", []))
    armhole = armholes.get(edge_index) if edge_index is not None else None
    if len(sampled_boundary) >= MINIMUM_CURVE_SAMPLE_COUNT:
        local_points = sampled_boundary
    elif (
        str(boundary.get("kind")) in {"arc", "bspline", "bezier", "curve"}
        and isinstance(armhole, dict)
    ):
        samples = cast("list[list[float]]", armhole.get("samples_local_mm", []))
        if len(samples) >= MINIMUM_CURVE_SAMPLE_COUNT:
            distance_forward = math.dist(samples[0], start)
            distance_reverse = math.dist(samples[-1], start)
            local_points = (
                samples if distance_forward <= distance_reverse else list(reversed(samples))
            )
    return edge_index, local_points, str(boundary.get("id", ""))


def _piece_boundary_geometry(
    boundaries: list[object],
    armholes: dict[int, dict[str, object]],
) -> tuple[list[list[float]], list[tuple[int | None, list[list[float]], str]]]:
    """Collect a piece's connected outline and individual sampled edges.

    Args:
        boundaries: Ordered boundary entries from a single piece.
        armholes: Armhole samples indexed by native edge index.

    Returns:
        Ordered outline coordinates and drawable edge records.
    """
    coords: list[list[float]] = []
    edge_shapes: list[tuple[int | None, list[list[float]], str]] = []
    for raw_boundary in boundaries:
        if not isinstance(raw_boundary, dict):
            continue
        edge_index, local_points, edge_id = _boundary_edge_shape(raw_boundary, armholes)
        edge_shapes.append((edge_index, local_points, edge_id))
        if (
            coords
            and math.dist(coords[-1], local_points[0]) <= BOUNDARY_POINT_CLOSURE_TOLERANCE_MM
        ):
            coords.extend(local_points[1:])
        else:
            coords.extend(local_points)
    if coords and math.dist(coords[0], coords[-1]) > BOUNDARY_POINT_CLOSURE_TOLERANCE_MM:
        coords.append(coords[0])
    return coords, edge_shapes


def _svg_transform_point(
    point: list[float], *, origin_x: float
) -> tuple[float, float]:
    """Map a local pattern-space coordinate into the SVG viewport.

    Args:
        point: Local two-dimensional pattern coordinate.
        origin_x: Horizontal offset for the current piece.

    Returns:
        SVG horizontal and vertical coordinates.
    """
    return origin_x + point[0] * 0.70, 600.0 - point[1] * 0.70


def _crossing_edge_colors(value: object) -> dict[int, str]:
    """Choose diagnostic colors for edges near a measured outline crossing.

    Args:
        value: Collection of near-crossing records from the pattern report.

    Returns:
        Edge-index to stroke-color mapping for the nearest reported crossings.
    """
    colors: dict[int, str] = {}
    for raw_nearby in _as_list(value):
        if (
            not isinstance(raw_nearby, dict)
            or float(raw_nearby.get("distance_mm", math.inf)) > CROSSING_DISTANCE_TOLERANCE_MM
        ):
            continue
        edge_match = re.search(r":edge:(\d+)$", str(raw_nearby.get("edge_id", "")))
        if edge_match:
            edge_index = int(edge_match.group(1))
            if edge_index not in colors:
                colors[edge_index] = "#cc3333" if not colors else "#e08a18"
    return colors


def _render_outline_path(coords: list[list[float]], origin_x: float) -> str | None:
    """Render the full piece outline when coordinate samples are available.

    Args:
        coords: Ordered, closed outline points in local pattern coordinates.
        origin_x: Horizontal offset for the current piece.

    Returns:
        SVG path element, or None when no outline points exist.
    """
    if not coords:
        return None
    first_x, first_y = _svg_transform_point(coords[0], origin_x=origin_x)
    path_data = [f"M {first_x:.3f},{first_y:.3f}"]
    for point in coords[1:]:
        px, py = _svg_transform_point(point, origin_x=origin_x)
        path_data.append(f"L {px:.3f},{py:.3f}")
    return (
        f'<path d="{" ".join(path_data)}" fill="#f8fafc" fill-opacity="0.65" '
        'stroke="#364152" stroke-width="1.8" stroke-linejoin="round"/>'
    )


def _render_edge_shapes(
    edge_shapes: list[tuple[int | None, list[list[float]], str]],
    colors: dict[int, str],
    origin_x: float,
    title_color: str,
) -> list[str]:
    """Render each sampled boundary edge and its diagnostic index label.

    Args:
        edge_shapes: Drawable edge records containing index, points, and identifier.
        colors: Edge stroke colors selected from near-crossing diagnostics.
        origin_x: Horizontal offset for the current piece.
        title_color: SVG color used for edge labels.

    Returns:
        Polyline and text elements for every sampled edge.
    """
    rendered: list[str] = []
    for edge_index, local_points, edge_id in edge_shapes:
        if not local_points:
            continue
        highlighted = edge_index is not None and edge_index in colors
        stroke = colors.get(edge_index, "#758195") if edge_index is not None else "#758195"
        points_to_draw = [
            _svg_transform_point(point, origin_x=origin_x) for point in local_points
        ]
        point_string = " ".join(f"{x:.3f},{y:.3f}" for x, y in points_to_draw)
        label_x, label_y = _svg_transform_point(
            local_points[len(local_points) // 2], origin_x=origin_x
        )
        label = f"e{edge_index}" if edge_index is not None else edge_id
        rendered.extend(
            [
                (
                    f'<polyline points="{point_string}" fill="none" stroke="{stroke}" '
                    f'stroke-width="{3.2 if highlighted else 1.6}" '
                    'stroke-linecap="round" stroke-linejoin="round"/>'
                ),
                (
                    f'<text x="{label_x:.3f}" y="{label_y - 7:.3f}" font-size="11" '
                    f'font-family="monospace" fill="{title_color}" text-anchor="middle">'
                    f"{html.escape(label)}</text>"
                ),
            ]
        )
    return rendered


def _render_crossing_marker(crossing: object, origin_x: float) -> list[str]:
    """Render a measured crossing crosshair when the report has local coordinates.

    Args:
        crossing: Candidate point record from a piece's topology findings.
        origin_x: Horizontal offset for the current piece.

    Returns:
        SVG marker elements or an empty list when no point is available.
    """
    if not isinstance(crossing, list) or len(crossing) < TWO_DIMENSIONAL_COORDINATE_COUNT:
        return []
    cx, cy = _svg_transform_point([float(crossing[0]), float(crossing[1])], origin_x=origin_x)
    return [
        (
            f'<circle cx="{cx:.3f}" cy="{cy:.3f}" r="7" fill="none" '
            'stroke="#cc2222" stroke-width="3"/>'
        ),
        (
            f'<path d="M {cx - 11:.3f},{cy:.3f} L {cx + 11:.3f},{cy:.3f} '
            f'M {cx:.3f},{cy - 11:.3f} L {cx:.3f},{cy + 11:.3f}" '
            'stroke="#cc2222" stroke-width="2"/>'
        ),
        (
            f'<text x="{origin_x:.3f}" y="637" font-size="13" '
            'font-family="sans-serif" fill="#cc2222">Crossing: '
            f"({float(crossing[0]):.3f}, {float(crossing[1]):.3f}) mm</text>"
        ),
    ]


def _render_piece_status(
    record: dict[str, object],
    piece_name: str,
    origin_x: float,
    title_color: str,
    crossing_edge_colors: dict[int, str],
) -> list[str]:
    """Render the validity labels and crossing-edge key for a single pattern piece.

    Args:
        record: Topology record corresponding to the piece.
        piece_name: Human-readable piece identifier.
        origin_x: Horizontal offset for the current piece.
        title_color: SVG color used for piece and validity labels.
        crossing_edge_colors: Highlight mapping for measured edge crossings.

    Returns:
        SVG text elements describing the piece status.
    """
    native_valid = bool(record.get("ir_valid"))
    derived_valid = bool(record.get("draft_valid"))
    valid = native_valid and derived_valid
    if valid:
        state = "VALID"
    elif not native_valid:
        state = "INVALID — NATIVE PATTERN TOPOLOGY"
    else:
        state = "INVALID — DERIVED OUTLINE REPRESENTATION"
    rendered = [
        (
            f'<text x="{origin_x:.3f}" y="26" font-size="17" font-weight="700" '
            f'font-family="sans-serif" fill="{title_color}">{html.escape(piece_name)}</text>'
        ),
        (
            f'<text x="{origin_x:.3f}" y="48" font-size="13" font-family="sans-serif" '
            f'fill="{"#237647" if valid else "#b42318"}">{html.escape(state)}</text>'
        ),
    ]
    if not valid:
        crossing_labels = ", ".join(f"e{value}" for value in crossing_edge_colors) or "not resolved"
        rendered.append(
            f'<text x="{origin_x:.3f}" y="68" font-size="11" font-family="sans-serif" '
            f'fill="#364152">Highlighted crossing edges: {html.escape(crossing_labels)}</text>'
        )
    return rendered


def _render_pattern_piece(
    raw_piece: dict[str, object],
    piece_number: int,
    armholes: dict[int, dict[str, object]],
) -> list[str]:
    """Render the outline, edge markers, and state labels for one garment piece.

    Args:
        raw_piece: Structured topology record for this piece.
        piece_number: Zero-based piece position used for stable panel placement.
        armholes: Armhole sample points indexed by native edge index.

    Returns:
        SVG elements associated with the piece.
    """
    record = raw_piece
    piece_name = str(record.get("piece", f"piece-{piece_number + 1}"))
    boundaries = _as_list(record.get("boundary_order"))
    origin_x = 34.0 + piece_number * 760.0
    coords, edge_shapes = _piece_boundary_geometry(boundaries, armholes)
    crossing_colors = _crossing_edge_colors(record.get("near_crossing"))
    rendered: list[str] = []
    outline = _render_outline_path(coords, origin_x)
    if outline is not None:
        rendered.append(outline)
    rendered.extend(_render_edge_shapes(edge_shapes, crossing_colors, origin_x, "#202938"))
    rendered.extend(_render_crossing_marker(record.get("crossing_local_mm"), origin_x))
    rendered.extend(_render_piece_status(record, piece_name, origin_x, "#202938", crossing_colors))
    return rendered


def render_pattern_svg(report: dict[str, object]) -> str:
    """Render the reported outline and highlight any measured self-intersection.

    Args:
        report: Structured scene-understanding report to render.

    Returns:
        Complete SVG markup visualizing the garment outline and findings.
    """
    pattern = _as_dict(report.get("pattern"))
    pieces = _as_list(pattern.get("pieces"))
    armholes = {
        int(item["edge_index"]): item
        for item in _as_list(pattern.get("native_armholes"))
        if isinstance(item, dict) and "edge_index" in item
    }
    pieces_rendered: list[str] = []
    for piece_number, raw_piece in enumerate(pieces[:2]):
        if isinstance(raw_piece, dict):
            pieces_rendered.extend(
                _render_pattern_piece(cast("dict[str, object]", raw_piece), piece_number, armholes)
            )
    if not pieces_rendered:
        pieces_rendered.append(
            '<text x="30" y="100" font-size="20" font-family="sans-serif" fill="#202938">'
            "No native pattern topology record was available in this run.</text>"
        )
    status = _as_dict(report.get("status"))
    result_text = str(status.get("result", "unknown")).upper()
    banner = (
        '<rect x="0" y="0" width="1510" height="660" fill="#ffffff"/>'
        f'<text x="34" y="656" font-size="11" font-family="sans-serif" fill="#667085">'
        f"Scene report result: {html.escape(result_text)}. Coordinates are panel-local "
        "millimetres. "
        "Raw screenshots are not altered.</text>"
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1510" height="660" viewBox="0 0 1510 660">'
        f"{banner}{''.join(pieces_rendered)}</svg>\n"
    )

def _render_fit_section(lines: list[str], report: dict[str, object]) -> None:
    """Render the fit-screening section without promoting heuristic warnings to failures.

    Args:
        lines: Markdown lines accumulated by the report renderer.
        report: Structured scene-understanding report data.
    """
    fit = _as_dict(report.get("fit_assessment"))
    fit_state = str(fit.get("state", "not_assessed"))
    fit_findings = _as_list(fit.get("findings"))
    fit_references = _as_dict(fit.get("reference_levels_mm"))
    fit_observed = _as_dict(fit.get("observed_final_panel_z_mm"))
    lines.extend(["", "## Fit and placement assessment", ""])
    lines.append(f"**Screening state:** {fit_state.upper().replace('_', ' ')}")
    if fit_state == "review_required":
        lines.extend(
            [
                (
                    "The execution and collision checks may have passed while garment coverage or "
                    "vertical placement remains suspicious."
                ),
                (
                    f"- Final panel Z range: {fit_observed.get('minimum')} to "
                    f"{fit_observed.get('maximum')} mm."
                ),
                (
                    f"- Declared hem Z: {fit_references.get('hem_z')} mm; shoulder reference Z: "
                    f"{fit_references.get('shoulder_z')} mm "
                    f"({fit_references.get('shoulder_reference_source', 'source unavailable')})."
                ),
            ]
        )
        for raw_finding in fit_findings:
            if not isinstance(raw_finding, dict):
                continue
            finding = cast("dict[str, object]", raw_finding)
            lines.append(
                f"- **WARNING — {finding.get('kind')}:** {finding.get('message')} "
                f"({finding.get('observed_mm')} mm; heuristic review threshold "
                f"{finding.get('review_threshold_mm')} mm)."
            )
    elif fit_state == "within_heuristic_tolerance":
        lines.append(
            "No large vertical-bounds deviation exceeded the screening threshold. This is not "
            "a fit or attachment certification."
        )
    else:
        lines.append(str(fit.get("reason", "No fit-alignment measurements were available.")))
    if fit.get("interpretation_limit"):
        lines.append(f"Limit: {fit.get('interpretation_limit')}")
    lines.append(f"Next action: {fit.get('next_action', report.get('next_action'))}")


def _render_geometry_issues(lines: list[str], report: dict[str, object]) -> None:
    """Render measured blocking pattern findings and their first repair action.

    Args:
        lines: Markdown lines accumulated by the report renderer.
        report: Structured scene-understanding report data.
    """
    issues = _as_list(report.get("issues"))
    lines.extend(["", "## Blocking geometry findings", ""])
    if issues:
        for raw_issue in issues:
            if not isinstance(raw_issue, dict):
                continue
            issue = cast("dict[str, object]", raw_issue)
            point = issue.get("point_local_mm")
            point_text = (
                f"({float(point[0]):.3f}, {float(point[1]):.3f}) mm"
                if isinstance(point, list) and len(point) >= TWO_DIMENSIONAL_COORDINATE_COUNT
                else "not reported"
            )
            edge_ids = (
                ", ".join(str(value) for value in _as_list(issue.get("edge_ids"))) or "not resolved"
            )
            lines.extend(
                [
                    (
                        f"- **BLOCKER — {issue.get('kind')} in {issue.get('piece')}:** "
                        f"{issue.get('reason')}. Crossing at local {point_text}; related edges: "
                        f"{edge_ids}."
                    ),
                    f"  - Effect: {issue.get('effect')}.",
                ]
            )
        lines.append(
            "- **Next action:** repair the pattern boundary; do not tune collision, timestep, "
            "or solver iterations."
        )
    else:
        lines.extend(
            [
                (
                    "No invalid polygon was reported. Topology validity is independent from body "
                    "coverage, placement, and attachment."
                ),
                f"Next action: {report.get('next_action')}",
            ]
        )


def _render_placement_section(lines: list[str], report: dict[str, object]) -> None:
    """Render observed panel placement values or the missing-evidence note.

    Args:
        lines: Markdown lines accumulated by the report renderer.
        report: Structured scene-understanding report data.
    """
    lines.extend(["", "## Placement observations", ""])
    placement = _as_dict(report.get("placement"))
    panels = _as_dict(placement.get("panels"))
    if panels:
        for side in sorted(panels):
            raw_panel = panels[side]
            if not isinstance(raw_panel, dict):
                continue
            panel = cast("dict[str, object]", raw_panel)
            lines.append(
                f"- **{side}:** panel origin Y = {panel.get('panel_origin_y_mm')} mm; "
                f"clearance used = {panel.get('configured_clearance_mm')} mm; "
                f"projected target vertices = {panel.get('projected_target_vertex_count')}."
            )
    else:
        lines.append("No explicit target-relative panel placement was observed.")


def _render_evidence_section(lines: list[str], report: dict[str, object]) -> None:
    """Render expected outputs and hashes for captured evidence.

    Args:
        lines: Markdown lines accumulated by the report renderer.
        report: Structured scene-understanding report data.
    """
    lines.extend(["", "## Evidence availability", ""])
    evidence = _as_dict(report.get("evidence"))
    expected = _as_dict(evidence.get("expected_or_known_outputs"))
    for name, value in expected.items():
        lines.append(f"- {name.replace('_', ' ')}: **{value}**")
    image_records = _as_list(evidence.get("images"))
    if image_records:
        lines.extend(["", "## Indexed images", ""])
        for raw_image in image_records:
            if not isinstance(raw_image, dict):
                continue
            image = cast("dict[str, object]", raw_image)
            lines.append(
                f"- {image.get('path')} — {image.get('size_bytes')} bytes; "
                f"SHA-256 hash: {image.get('sha256')}"
            )


def render_markdown(report: dict[str, object]) -> str:
    """Generate a readable summary that leads with the blocker, not solver metrics.

    Args:
        report: Structured scene-understanding report to summarize.

    Returns:
        Markdown document explaining the run status and gathered evidence.
    """
    status = _as_dict(report.get("status"))
    stages = _as_dict(report.get("stages"))
    lines = [
        "# Workflow scene-understanding report",
        "",
        f"**Result:** {str(status.get('result', 'unknown')).upper()}",
        f"**First failed stage:** {status.get('failed_stage') or 'not identified'}",
        f"**Last completed stage:** {status.get('last_completed_stage', 'unknown')}",
        "",
        "## Stage state",
        "",
        "| Stage | State |",
        "|---|---|",
    ]
    lines.extend(
        f"| {stage_name.replace('_', ' ')} | {stages.get(stage_name, 'not_observed')} |"
        for stage_name in (
            "mannequin_pose",
            "pattern_construction",
            "pattern_topology",
            "sewing_preview",
            "initial_placement",
            "simulation",
            "drape",
        )
    )
    _render_fit_section(lines, report)

    _render_geometry_issues(lines, report)

    _render_placement_section(lines, report)

    _render_evidence_section(lines, report)

    lines.extend(
        [
            "",
            "## Interpretation guard",
            "",
            (
                "A generated screenshot is not proof that its input geometry is valid. A stage "
                "marked not_reached has no downstream simulation result. Diagnose native geometry, "
                "coordinate frames, semantic topology, placement, and attachments before numerical "
                "settings."
            ),
            "",
            (
                "This report was derived only from files in the GitHub Actions workspace for this "
                "run. It does not inspect a live FreeCAD session or query an external service."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def write_report(progress_path: Path, output_root: Path, workspace: Path) -> dict[str, object]:
    """Write JSON, Markdown, and annotated SVG reports into the uploaded artifact directory.

    Args:
        progress_path: Path to the captured workflow progress log.
        output_root: Directory where report artifacts are written.
        workspace: Root path used to resolve evidence file paths.

    Returns:
        Structured report written to the JSON and Markdown artifacts.
    """
    output_root.mkdir(parents=True, exist_ok=True)
    report = build_report(progress_path, output_root, workspace)
    svg_path = output_root / "scene-understanding.svg"
    svg_path.write_text(render_pattern_svg(report), encoding="utf-8")
    json_path = output_root / "scene-understanding.json"
    markdown_path = output_root / "scene-understanding.md"
    json_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return report


def main() -> int:
    """Run as a best-effort post-FreeCAD reporter; absence of logs is reported, not hidden.

    Returns:
        Process status indicating whether report generation succeeded.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--progress", type=Path, default=Path("docs/images/generated/gui-progress.log")
    )
    parser.add_argument("--output-root", type=Path, default=Path("docs/images/generated"))
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    args = parser.parse_args()
    report = write_report(args.progress, args.output_root, args.workspace)
    status = _as_dict(report.get("status"))
    sys.stdout.write(
        "scene-understanding-report=written "
        f"result={status.get('result')} failed-stage={status.get('failed_stage') or 'none'}\n"
    )
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
