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
import re
from pathlib import Path
from typing import cast

SCHEMA = "freecad-cloth.scene-understanding"
SCHEMA_VERSION = 1

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


def _literal_tuple(value: str) -> tuple[object, ...]:
    """Safely parse a tuple-like value written by Python's diagnostic repr."""
    parsed = ast.literal_eval(value)
    if not isinstance(parsed, tuple):
        raise ValueError("expected a tuple in the workflow diagnostic")
    return cast(tuple[object, ...], parsed)


def _point(value: object) -> list[float]:
    """Normalize a 2D point to a JSON-safe list of finite floats."""
    if not isinstance(value, (tuple, list)) or len(value) < 2:
        raise ValueError("invalid 2D point in topology diagnostics")
    result = [float(value[0]), float(value[1])]
    if not all(math.isfinite(item) for item in result):
        raise ValueError("non-finite point in topology diagnostics")
    return result


def _pair(value: str) -> list[float]:
    """Parse a point or bounding interval encoded using Python tuple syntax."""
    return _point(_literal_tuple(value))


def _parse_topology(line: str) -> dict[str, object] | None:
    """Extract the authoritative sampled boundary and nearest crossing segments."""
    match = _TOPOLOGY_RE.search(line)
    if match is None:
        return None
    raw_boundaries = _literal_tuple(match.group(8))
    boundaries: list[dict[str, object]] = []
    for item in raw_boundaries:
        if not isinstance(item, tuple) or len(item) != 5:
            continue
        edge_name = str(item[0])
        edge_match = re.search(r":edge:(\d+)$", edge_name)
        boundaries.append(
            {
                "id": edge_name,
                "edge_index": int(edge_match.group(1)) if edge_match else None,
                "kind": str(item[1]),
                "sample_count": int(item[2]),
                "start_mm": _point(item[3]),
                "end_mm": _point(item[4]),
            }
        )
    raw_nearby = _literal_tuple(match.group(9))
    nearby: list[dict[str, object]] = []
    for item in raw_nearby:
        if not isinstance(item, tuple) or len(item) != 5:
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
        [float(crossing_match.group(1)), float(crossing_match.group(2))]
        if crossing_match
        else None
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
    """Extract the native curve class, parameter interval, and sampled local shape."""
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
    """Hash rendered evidence already emitted by the run; never modify source images."""
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


def build_report(progress_path: Path, output_root: Path, workspace: Path) -> dict[str, object]:
    """Build a machine-readable diagnosis using only the completed workflow files."""
    progress_text = (
        progress_path.read_text(encoding="utf-8", errors="replace")
        if progress_path.is_file()
        else ""
    )
    topology_by_piece: dict[str, dict[str, object]] = {}
    armholes_by_index: dict[int, dict[str, object]] = {}
    placements_by_side: dict[str, dict[str, object]] = {}
    pose: dict[str, float] | None = None
    screenshot_states: dict[str, dict[str, object]] = {}
    drape_records: list[dict[str, object]] = []
    failure_lines: list[str] = []
    has_scenario_pass = False
    has_simulation_start = "tunic-simulation-start" in progress_text
    for line in progress_text.splitlines():
        topology = _parse_topology(line)
        if topology is not None:
            topology_by_piece[str(topology["piece"])] = topology
        armhole = _parse_armhole(line)
        if armhole is not None:
            armholes_by_index[int(armhole["edge_index"])] = armhole
        pose_match = _POSE_RE.search(line)
        if pose_match:
            pose = {
                "left_shoulder_wrist_dx_mm": float(pose_match.group(1)),
                "left_shoulder_wrist_dz_mm": float(pose_match.group(2)),
                "right_shoulder_wrist_dx_mm": float(pose_match.group(3)),
                "right_shoulder_wrist_dz_mm": float(pose_match.group(4)),
            }
        placement_match = _PLACEMENT_RE.search(line)
        if placement_match:
            placements_by_side[placement_match.group(1)] = {
                "projected_target_y_range_mm": [
                    float(placement_match.group(2)),
                    float(placement_match.group(3)),
                ],
                "panel_origin_y_mm": float(placement_match.group(4)),
                "configured_clearance_mm": float(placement_match.group(5)),
                "torso_x_range_mm": [
                    float(placement_match.group(6)),
                    float(placement_match.group(7)),
                ],
                "projected_target_vertex_count": int(placement_match.group(8)),
            }
        screenshot = _SCREENSHOT_RE.search(line)
        if screenshot:
            raw_path = screenshot.group(1).strip()
            image_name = Path(raw_path.replace("/workspace/", "")).name
            screenshot_states[image_name] = {
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
                drape_records.append(cast(dict[str, object], parsed_metrics))
        if "scenario-pass" in line or "tunic-audit-process-exit=success" in line:
            has_scenario_pass = True
        if "scenario-fail" in line or line.startswith("SCENARIO FAILURE:"):
            failure_lines.append(line.strip())

    topology_records = list(topology_by_piece.values())
    invalid_topology = [
        record for record in topology_records if not bool(record["ir_valid"]) or not bool(record["draft_valid"])
    ]
    failure_text = "\n".join(failure_lines)
    failure_unknown = bool(failure_lines) and not invalid_topology
    if invalid_topology:
        result = "blocked"
        failed_stage = "pattern_topology"
        last_completed_stage = "pattern_geometry_created"
        next_action = (
            "Repair the native panel outline so it is a simple polygon. Inspect the two "
            "reported crossing edges and local intersection coordinate. Do not change solver settings."
        )
    elif has_scenario_pass and not failure_lines:
        result = "passed"
        failed_stage = None
        last_completed_stage = "drape" if drape_records else "simulation"
        next_action = "Review final multi-view fit and keep the same strict geometry and collision gates."
    elif failure_lines:
        result = "failed"
        failed_stage = "unknown_from_available_markers" if failure_unknown else "simulation_or_later"
        last_completed_stage = "simulation_started" if has_simulation_start else "last_observed_stage"
        next_action = (
            "Use the failure log and the last completed stage to localize the first failing invariant "
            "before changing any parameter."
        )
    else:
        result = "incomplete"
        failed_stage = None
        last_completed_stage = "unknown"
        next_action = "Inspect available workflow output; the progress log did not record a terminal stage."

    avatar_image_present = any(
        "cloth-mannequin-near-t-pose.png" in name for name in screenshot_states
    ) or (output_root / "cloth-mannequin-near-t-pose.png").is_file()
    pattern_image_present = (output_root / "cloth-pattern-design.png").is_file()
    sewing_image_present = (output_root / "cloth-sewing.png").is_file()
    drape_image_present = any(output_root.glob("cloth-simulation-draped*.png"))
    if pose is not None and avatar_image_present:
        pose_state = "passed"
    elif pose is not None:
        pose_state = "measured_but_image_not_found"
    else:
        pose_state = "not_observed"
    pattern_state = "invalid" if invalid_topology else (
        "valid" if topology_records and all(bool(item["ir_valid"]) for item in topology_records) else "not_observed"
    )
    sewing_state = (
        "generated_from_invalid_input"
        if invalid_topology and sewing_image_present
        else "generated"
        if sewing_image_present
        else "not_reached_or_not_captured"
    )
    if invalid_topology:
        simulation_state = "not_reached"
    elif has_simulation_start:
        simulation_state = "started"
    else:
        simulation_state = "not_observed"
    if drape_records or drape_image_present:
        drape_state = "evidence_present"
    elif invalid_topology or not has_simulation_start:
        drape_state = "not_reached_or_not_captured"
    else:
        drape_state = "started_but_final_evidence_missing"

    issues: list[dict[str, object]] = []
    for topology in invalid_topology:
        nearby = cast(list[dict[str, object]], topology["near_crossing"])
        touching = list(
            dict.fromkeys(
                str(item["edge_id"])
                for item in nearby
                if float(item["distance_mm"]) <= 1e-6
            )
        )
        issues.append(
            {
                "kind": "self_intersection",
                "severity": "blocker",
                "piece": topology["piece"],
                "reason": topology["ir_reason"],
                "edge_ids": touching,
                "point_local_mm": topology["crossing_local_mm"],
                "source": "PatternIR sampled boundary and polygon validity diagnostic",
                "effect": "pattern, seam preview, and any later fitting derived from this outline are not valid fit evidence",
            }
        )

    image_inventory = _image_inventory(output_root, workspace)
    metrics_path = output_root / "drape-visual-metrics.json"
    metrics_payload: object = None
    if metrics_path.is_file():
        try:
            metrics_payload = json.loads(metrics_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            metrics_payload = {"parse_error": "drape-visual-metrics.json is not valid JSON"}
    crossings = [
        {
            "piece": record["piece"],
            "point_local_mm": record["crossing_local_mm"],
            "edge_ids": [
                item["edge_id"]
                for item in cast(list[dict[str, object]], record["near_crossing"])
                if float(item["distance_mm"]) <= 1e-6
            ],
        }
        for record in invalid_topology
    ]

    return {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "status": {
            "result": result,
            "failed_stage": failed_stage,
            "last_completed_stage": last_completed_stage,
            "failure_text": failure_text or None,
        },
        "units": {
            "length": "mm",
            "pattern_coordinates": "piece-local 2D",
            "pose_and_placement_coordinates": "FreeCAD world coordinates when specified by the producer",
        },
        "stages": {
            "mannequin_pose": pose_state,
            "pattern_construction": "captured" if topology_records or pattern_image_present else "not_observed",
            "pattern_topology": pattern_state,
            "sewing_preview": sewing_state,
            "initial_placement": "measured" if placements_by_side else "not_observed",
            "simulation": simulation_state,
            "drape": drape_state,
        },
        "mannequin_pose_measurements": pose,
        "pattern": {
            "pieces": topology_records,
            "native_armholes": [armholes_by_index[key] for key in sorted(armholes_by_index)],
            "crossings": crossings,
        },
        "placement": {
            "panels": placements_by_side,
            "initial_target_clearance_log_lines": [
                line.strip()
                for line in progress_text.splitlines()
                if "step0-target-vertex-clearance-mm=" in line
            ],
        },
        "simulation": {
            "started": has_simulation_start,
            "drape_metrics_from_log": drape_records,
            "drape_metrics_json": metrics_payload,
        },
        "issues": issues,
        "next_action": next_action,
        "evidence": {
            "images": image_inventory,
            "screenshot_log_entries": screenshot_states,
            "expected_or_known_outputs": {
                "mannequin_pose": "present" if avatar_image_present else "missing",
                "pattern_design": "present" if pattern_image_present else "missing",
                "sewing_preview": "present" if sewing_image_present else "missing",
                "post_drape_views": "present" if drape_image_present else "missing",
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
    """Return a dict for a previously validated report section."""
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


def _as_list(value: object) -> list[object]:
    """Return a list for a previously validated report section."""
    return cast(list[object], value) if isinstance(value, list) else []


def render_pattern_svg(report: dict[str, object]) -> str:
    """Render the reported outline and highlight any measured self-intersection."""
    pattern = _as_dict(report.get("pattern"))
    pieces = _as_list(pattern.get("pieces"))
    armholes = {
        int(item["edge_index"]): item
        for item in _as_list(pattern.get("native_armholes"))
        if isinstance(item, dict) and "edge_index" in item
    }
    title_color = "#202938"
    pieces_rendered: list[str] = []
    scale = 0.70
    panel_offset = 760.0
    base_y = 600.0
    for piece_number, raw_piece in enumerate(pieces[:2]):
        if not isinstance(raw_piece, dict):
            continue
        record = cast(dict[str, object], raw_piece)
        piece_name = str(record.get("piece", f"piece-{piece_number + 1}"))
        boundaries = _as_list(record.get("boundary_order"))
        origin_x = 34.0 + piece_number * panel_offset
        coords: list[list[float]] = []
        edge_shapes: list[tuple[int | None, list[list[float]], str]] = []
        for raw_boundary in boundaries:
            if not isinstance(raw_boundary, dict):
                continue
            boundary = cast(dict[str, object], raw_boundary)
            edge_index_value = boundary.get("edge_index")
            edge_index = int(edge_index_value) if isinstance(edge_index_value, int) else None
            start = _point(boundary.get("start_mm"))
            end = _point(boundary.get("end_mm"))
            local_points = [start, end]
            armhole = armholes.get(edge_index) if edge_index is not None else None
            if str(boundary.get("kind")) == "arc" and isinstance(armhole, dict):
                samples = cast(list[list[float]], armhole.get("samples_local_mm", []))
                if len(samples) >= 2:
                    distance_forward = math.dist(samples[0], start)
                    distance_reverse = math.dist(samples[-1], start)
                    local_points = samples if distance_forward <= distance_reverse else list(reversed(samples))
            edge_shapes.append((edge_index, local_points, str(boundary.get("id", ""))))
            if coords and math.dist(coords[-1], local_points[0]) <= 1e-5:
                coords.extend(local_points[1:])
            else:
                coords.extend(local_points)
        if coords and math.dist(coords[0], coords[-1]) > 1e-5:
            coords.append(coords[0])

        def transform(point: list[float]) -> tuple[float, float]:
            return origin_x + point[0] * scale, base_y - point[1] * scale

        if coords:
            first_x, first_y = transform(coords[0])
            path_data = [f"M {first_x:.3f},{first_y:.3f}"]
            for point in coords[1:]:
                px, py = transform(point)
                path_data.append(f"L {px:.3f},{py:.3f}")
            pieces_rendered.append(
                f'<path d="{" ".join(path_data)}" fill="#f8fafc" fill-opacity="0.65" '
                f'stroke="#364152" stroke-width="1.8" stroke-linejoin="round"/>'
            )
        for edge_index, local_points, edge_id in edge_shapes:
            if not local_points:
                continue
            highlighted = edge_index in {2, 3, 5, 6} and bool(record.get("crossing_local_mm"))
            stroke = "#cc3333" if edge_index == 3 else "#e08a18" if edge_index == 2 else "#758195"
            if not highlighted:
                stroke = "#758195"
            points_to_draw = [transform(point) for point in local_points]
            point_string = " ".join(f"{x:.3f},{y:.3f}" for x, y in points_to_draw)
            pieces_rendered.append(
                f'<polyline points="{point_string}" fill="none" stroke="{stroke}" '
                f'stroke-width="{3.2 if edge_index in {2, 3} and highlighted else 1.6}" '
                f'stroke-linecap="round" stroke-linejoin="round"/>'
            )
            mid = local_points[len(local_points) // 2]
            label_x, label_y = transform(mid)
            label = f"e{edge_index}" if edge_index is not None else edge_id
            pieces_rendered.append(
                f'<text x="{label_x:.3f}" y="{label_y - 7:.3f}" font-size="11" '
                f'font-family="monospace" fill="{title_color}" text-anchor="middle">{html.escape(label)}</text>'
            )
        crossing = record.get("crossing_local_mm")
        if isinstance(crossing, list) and len(crossing) >= 2:
            cx, cy = transform([float(crossing[0]), float(crossing[1])])
            pieces_rendered.extend(
                [
                    f'<circle cx="{cx:.3f}" cy="{cy:.3f}" r="7" fill="none" stroke="#cc2222" stroke-width="3"/>',
                    f'<path d="M {cx - 11:.3f},{cy:.3f} L {cx + 11:.3f},{cy:.3f} M {cx:.3f},{cy - 11:.3f} L {cx:.3f},{cy + 11:.3f}" stroke="#cc2222" stroke-width="2"/>',
                    f'<text x="{origin_x:.3f}" y="637" font-size="13" font-family="sans-serif" fill="#cc2222">Crossing: ({float(crossing[0]):.3f}, {float(crossing[1]):.3f}) mm</text>',
                ]
            )
        valid = bool(record.get("ir_valid")) and bool(record.get("draft_valid"))
        state = "VALID" if valid else "INVALID — SELF-INTERSECTION"
        pieces_rendered.append(
            f'<text x="{origin_x:.3f}" y="26" font-size="17" font-weight="700" '
            f'font-family="sans-serif" fill="{title_color}">{html.escape(piece_name)}</text>'
        )
        pieces_rendered.append(
            f'<text x="{origin_x:.3f}" y="48" font-size="13" font-family="sans-serif" '
            f'fill="{"#237647" if valid else "#b42318"}">{html.escape(state)}</text>'
        )
        if not valid:
            pieces_rendered.append(
                f'<text x="{origin_x:.3f}" y="68" font-size="11" font-family="sans-serif" fill="#364152">'
                "Red: shoulder edge 3; amber: armhole edge 2</text>"
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
        f"Scene report result: {html.escape(result_text)}. Coordinates are panel-local millimetres. "
        "Raw screenshots are not altered.</text>"
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1510" height="660" viewBox="0 0 1510 660">'
        f"{banner}{''.join(pieces_rendered)}</svg>\n"
    )


def render_markdown(report: dict[str, object]) -> str:
    """Generate a readable summary that leads with the blocker, not solver metrics."""
    status = _as_dict(report.get("status"))
    stages = _as_dict(report.get("stages"))
    placement = _as_dict(report.get("placement"))
    evidence = _as_dict(report.get("evidence"))
    expected = _as_dict(evidence.get("expected_or_known_outputs"))
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
    for stage_name in (
        "mannequin_pose",
        "pattern_construction",
        "pattern_topology",
        "sewing_preview",
        "initial_placement",
        "simulation",
        "drape",
    ):
        lines.append(f"| {stage_name.replace('_', ' ')} | {stages.get(stage_name, 'not_observed')} |")
    issues = _as_list(report.get("issues"))
    lines.extend(["", "## Blocking geometry findings", ""])
    if issues:
        for raw_issue in issues:
            if not isinstance(raw_issue, dict):
                continue
            issue = cast(dict[str, object], raw_issue)
            point = issue.get("point_local_mm")
            point_text = (
                f"({float(point[0]):.3f}, {float(point[1]):.3f}) mm"
                if isinstance(point, list) and len(point) >= 2
                else "not reported"
            )
            edge_ids = ", ".join(str(value) for value in _as_list(issue.get("edge_ids"))) or "not resolved"
            lines.append(
                f"- **BLOCKER — {issue.get('kind')} in {issue.get('piece')}:** {issue.get('reason')}. "
                f"Crossing at local {point_text}; related edges: {edge_ids}."
            )
            lines.append(f"  - Effect: {issue.get('effect')}.")
        lines.append("- **Next action:** repair the pattern boundary; do not tune collision, timestep, or solver iterations.")
    else:
        lines.append("No invalid polygon was reported. This does not imply a successful fit; inspect the stage table and available measurements.")
        lines.append(f"Next action: {report.get('next_action')}")
    lines.extend(["", "## Placement observations", ""])
    panels = _as_dict(placement.get("panels"))
    if panels:
        for side in sorted(panels):
            raw_panel = panels[side]
            if not isinstance(raw_panel, dict):
                continue
            panel = cast(dict[str, object], raw_panel)
            lines.append(
                f"- **{side}:** panel origin Y = {panel.get('panel_origin_y_mm')} mm; "
                f"clearance used = {panel.get('configured_clearance_mm')} mm; "
                f"projected target vertices = {panel.get('projected_target_vertex_count')}."
            )
    else:
        lines.append("No explicit target-relative panel placement was observed.")
    lines.extend(["", "## Evidence availability", ""])
    for name, value in expected.items():
        lines.append(f"- {name.replace('_', ' ')}: **{value}**")
    image_records = _as_list(evidence.get("images"))
    if image_records:
        lines.extend(["", "## Indexed images", ""])
        for raw_image in image_records:
            if not isinstance(raw_image, dict):
                continue
            image = cast(dict[str, object], raw_image)
            lines.append(
                f"- {image.get('path')} — {image.get('size_bytes')} bytes; "
                f"SHA-256 hash: {image.get('sha256')}"
            )
    lines.extend(
        [
            "",
            "## Interpretation guard",
            "",
            "A generated screenshot is not proof that its input geometry is valid. A stage marked "
            "not_reached has no downstream simulation result. Diagnose native geometry, coordinate "
            "frames, semantic topology, placement, and attachments before numerical settings.",
            "",
            "This report was derived only from files in the GitHub Actions workspace for this run. "
            "It does not inspect a live FreeCAD session or query an external service.",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(progress_path: Path, output_root: Path, workspace: Path) -> dict[str, object]:
    """Write JSON, Markdown, and annotated SVG reports into the uploaded artifact directory."""
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
    """Run as a best-effort post-FreeCAD reporter; absence of logs is reported, not hidden."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--progress", type=Path, default=Path("docs/images/generated/gui-progress.log"))
    parser.add_argument("--output-root", type=Path, default=Path("docs/images/generated"))
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    args = parser.parse_args()
    report = write_report(args.progress, args.output_root, args.workspace)
    status = _as_dict(report.get("status"))
    print(
        "scene-understanding-report=written result=%s failed-stage=%s"
        % (status.get("result"), status.get("failed_stage") or "none"),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
