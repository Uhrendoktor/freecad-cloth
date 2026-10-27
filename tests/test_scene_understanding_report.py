# Copyright (C) 2026 FreeCAD Cloth contributors
"""Tests for artifact-only scene diagnosis and geometry annotation."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from tests.support.assertions import require
from tools.ci.scene_understanding_report import (
    _float_value,
    _int_value,
    write_report,
)

if TYPE_CHECKING:
    from pathlib import Path


def _expect_dict(value: object, *, message: str) -> dict[str, object]:
    """Validate and normalize one dictionary-shaped value from the scene report.

    Args:
        value: Candidate report value that should contain string keys.
        message: Diagnostic for a value that does not satisfy the dictionary contract.

    Returns:
        A dictionary with string keys and object-valued entries.

    Raises:
        AssertionError: If the value is not a dictionary or contains a non-string key.
    """
    if not isinstance(value, dict):
        raise AssertionError(message)
    normalized: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise AssertionError(f"{message} Dictionary keys must be strings.")
        normalized[key] = item
    return normalized


def _expect_list(value: object, *, message: str) -> list[object]:
    """Validate and copy one list-shaped value from the scene report.

    Args:
        value: Candidate report value that should be a list.
        message: Diagnostic for a value that does not satisfy the list contract.

    Returns:
        The list items with object element types for further validation.

    Raises:
        AssertionError: If the value is not a list.
    """
    if not isinstance(value, list):
        raise AssertionError(message)
    normalized: list[object] = []
    for item in value:
        normalized.append(item)
    return normalized


def test_float_value_accepts_integer_and_float_literals() -> None:
    """Preserve numeric diagnostic values when normalizing them to floats."""
    require(
        condition=_float_value(3) == 3.0 and _float_value(2.5) == 2.5,
        message="Valid integer and float diagnostic values must retain their value.",
    )


@pytest.mark.parametrize("value", [True, "1.5", None])
def test_float_value_rejects_non_numeric_literals(value: object) -> None:
    """Reject diagnostic values that cannot be trusted as numeric literals.

    Args:
        value: Candidate value that is not an integer or floating-point literal.
    """
    with pytest.raises(TypeError, match="numeric value"):
        _float_value(value)


@pytest.mark.parametrize("value", [True, 2.5, "2"])
def test_int_value_rejects_non_integer_literals(value: object) -> None:
    """Reject diagnostic values that are not exact integer literals.

    Args:
        value: Candidate value that is not an integer literal.
    """
    with pytest.raises(TypeError, match="integer value"):
        _int_value(value)


def _invalid_topology_log() -> str:
    """Build geometric facts from the PR #2674 workflow artifact.

    Returns:
        Progress-log text containing an invalid topology record and nearby crossings.
    """
    boundaries = (
        ("pattern-piece-1:edge:0", "line", 2, (711.111, 0.0), (0.0, 0.0)),
        ("pattern-piece-1:edge:7", "line", 2, (0.0, 0.0), (229.333, 302.4)),
        ("pattern-piece-1:edge:6", "arc", 64, (229.333, 302.4), (77.867, 481.6)),
        ("pattern-piece-1:edge:5", "line", 2, (77.867, 481.6), (267.2, 526.4)),
        ("pattern-piece-1:edge:4", "line", 2, (267.2, 526.4), (443.911, 526.4)),
        ("pattern-piece-1:edge:3", "line", 2, (443.911, 526.4), (633.244, 481.6)),
        ("pattern-piece-1:edge:2", "arc", 64, (633.244, 481.6), (481.778, 302.4)),
        ("pattern-piece-1:edge:1", "line", 2, (481.778, 302.4), (711.111, 0.0)),
    )
    nearby = (
        (0.0, 67, "pattern-piece-1:edge:3", (443.911, 526.4), (633.244, 481.6)),
        (0.0, 69, "pattern-piece-1:edge:2", (628.732, 482.693), (624.184, 483.625)),
    )
    return (
        "tunic-outline-topology piece=VisualTunicFront ir-valid=False "
        "ir-reason=Self-intersection[627.926235325921 482.858393143538] "
        "draft-valid=False draft-reason=Self-intersection[627.926235325921 482.858393143538] "
        f"ir-points=132 draft-points=132 boundary-order={boundaries!r} near-crossing={nearby!r}"
    )


def _armhole_log(
    index: int,
    start: tuple[float, float],
    end: tuple[float, float],
    samples: tuple[tuple[float, float], ...],
) -> str:
    """Format a native armhole sample record.

    Args:
        index: Native curve boundary index.
        start: First armhole coordinate in local millimetres.
        end: Last armhole coordinate in local millimetres.
        samples: Ordered curve sample coordinates in local millimetres.

    Returns:
        One progress-log line containing native armhole measurements.
    """
    bounds = (
        min(point[0] for point in samples),
        min(point[1] for point in samples),
        max(point[0] for point in samples),
        max(point[1] for point in samples),
    )
    return (
        f"tunic-native-armhole index={index} type=ArcOfCircle range=(0.0, 2.0) "
        f"start={start!r} end={end!r} bounds={bounds!r} inward-scoop=96.805 samples={samples!r}"
    )


def test_invalid_outline_becomes_blocking_scene_diagnosis(tmp_path: Path) -> None:
    """Identify topology as the blocker without claiming a drape result.

    Args:
        tmp_path: Pytest-managed temporary directory for report fixtures and outputs.
    """
    workspace = tmp_path
    output_root = workspace / "docs" / "images" / "generated"
    output_root.mkdir(parents=True)
    (output_root / "cloth-mannequin-near-t-pose.png").write_bytes(b"test-png-pose")
    (output_root / "cloth-pattern-design.png").write_bytes(b"test-png-pattern")
    (output_root / "cloth-sewing.png").write_bytes(b"test-png-sewing")
    progress = output_root / "gui-progress.log"
    arc_2 = (
        (481.778, 302.4),
        (471.581, 373.846),
        (501.046, 439.726),
        (561.098, 479.753),
        (633.244, 481.6),
    )
    arc_6 = (
        (77.867, 481.6),
        (150.013, 479.753),
        (210.065, 439.726),
        (239.53, 373.846),
        (229.333, 302.4),
    )
    progress.write_text(
        "\n".join(
            (
                "script-start",
                "tunic-pose-geometry left_dx=239.6 left_dz=50.9 right_dx=239.6 right_dz=50.9",
                _armhole_log(2, arc_2[0], arc_2[-1], arc_2),
                _armhole_log(6, arc_6[0], arc_6[-1], arc_6),
                _invalid_topology_log(),
                "screenshot=/workspace/docs/images/generated/"
                "cloth-mannequin-near-t-pose.png state=pose bytes=13",
                "screenshot=/workspace/docs/images/generated/"
                "cloth-pattern-design.png state=pattern bytes=16",
                "screenshot=/workspace/docs/images/generated/"
                "cloth-sewing.png state=sewing bytes=14",
                "scenario-fail exception=ValueError('pattern boundary self-intersects')",
                "script-end exit-code=1",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    report = write_report(progress, output_root, workspace)

    status = _expect_dict(report["status"], message="Report status must be a dictionary.")
    stages = _expect_dict(report["stages"], message="Report stages must be a dictionary.")
    require(
        condition=status["result"] == "blocked",
        message="Invalid topology must produce a blocked report.",
    )
    require(
        condition=status["failed_stage"] == "pattern_topology",
        message="Invalid native topology must identify the failed stage.",
    )
    require(
        condition=stages["pattern_topology"] == "invalid",
        message="Invalid native topology must be recorded in the stage summary.",
    )
    require(
        condition=stages["simulation"] == "not_reached",
        message="Simulation must not be reported as reached after a topology blocker.",
    )
    require(
        condition=stages["drape"] == "not_reached",
        message="Drape must not be reported as reached after a topology blocker.",
    )
    issues = _expect_list(report["issues"], message="Report issues must be a list.")
    require(
        condition=len(issues) == 1,
        message="The invalid outline should produce exactly one issue.",
    )
    issue = _expect_dict(issues[0], message="Each report issue must be a dictionary.")
    require(
        condition=issue["edge_ids"] == ["pattern-piece-1:edge:3", "pattern-piece-1:edge:2"],
        message="The report must identify both nearby crossing edges.",
    )
    require(
        condition=issue["point_local_mm"] == [627.926235325921, 482.858393143538],
        message="The report must retain the measured crossing point.",
    )

    written = json.loads((output_root / "scene-understanding.json").read_text(encoding="utf-8"))
    require(
        condition=written["status"]["failed_stage"] == "pattern_topology",
        message="Written JSON must preserve the failed stage.",
    )
    markdown = (output_root / "scene-understanding.md").read_text(encoding="utf-8")
    require(
        condition="do not tune collision" in markdown,
        message="The report must prioritize topology before collision tuning.",
    )
    svg = (output_root / "scene-understanding.svg").read_text(encoding="utf-8")
    require(
        condition="627.926" in svg,
        message="The SVG must annotate the measured topology crossing.",
    )
    require(
        condition="INVALID" in svg,
        message="The SVG must label invalid pattern geometry.",
    )
    require(
        condition='stroke="#cc3333"' in svg,
        message="The SVG must use the invalid-geometry diagnostic color.",
    )


def test_missing_progress_log_emits_explicit_incomplete_dossier(tmp_path: Path) -> None:
    """Leave an explicit incomplete report when an early crash prevents observations.

    Args:
        tmp_path: Pytest-managed temporary directory for report fixtures and outputs.
    """
    output_root = tmp_path / "docs" / "images" / "generated"
    report = write_report(tmp_path / "missing.log", output_root, tmp_path)

    status = _expect_dict(report["status"], message="Report status must be a dictionary.")
    stages = _expect_dict(report["stages"], message="Report stages must be a dictionary.")
    require(
        condition=status["result"] == "incomplete",
        message="Missing progress evidence must produce an incomplete report.",
    )
    require(
        condition=status["failed_stage"] is None,
        message="Successful and incomplete reports must not invent a failed stage.",
    )
    require(
        condition=stages["simulation"] == "not_observed",
        message="Scene report predicate failed: stages['simulation'] == 'not_observed'.",
    )
    require(
        condition=(output_root / "scene-understanding.json").is_file(),
        message="The scene report must emit every expected output file.",
    )
    require(
        condition=(output_root / "scene-understanding.md").is_file(),
        message="The scene report must emit every expected output file.",
    )
    require(
        condition=(output_root / "scene-understanding.svg").is_file(),
        message="The scene report must emit every expected output file.",
    )


def test_success_status_does_not_invent_a_topology_failure(tmp_path: Path) -> None:
    """Retain neutral stage facts after successful execution without inventing blockers.

    Args:
        tmp_path: Pytest-managed temporary directory for report fixtures and outputs.
    """
    output_root = tmp_path / "docs" / "images" / "generated"
    output_root.mkdir(parents=True)
    progress = output_root / "gui-progress.log"
    progress.write_text(
        "script-start\nscenario-pass\ntunic-audit-process-exit=success\n",
        encoding="utf-8",
    )

    report = write_report(progress, output_root, tmp_path)

    status = _expect_dict(report["status"], message="Report status must be a dictionary.")
    require(
        condition=status["result"] == "passed",
        message="A successful run must retain its passed result.",
    )
    require(
        condition=status["failed_stage"] is None,
        message="Successful and incomplete reports must not invent a failed stage.",
    )
    require(
        condition=report["issues"] == [],
        message="A successful run must not invent topology issues.",
    )
    fit_assessment = _expect_dict(
        report["fit_assessment"],
        message="Fit assessment must be a dictionary.",
    )
    require(
        condition=fit_assessment["state"] == "not_assessed",
        message="Fit without final measurements must remain not assessed.",
    )


def test_successful_execution_with_bad_vertical_coverage_requires_fit_review(
    tmp_path: Path,
) -> None:
    """Require fit review when a successful run has insufficient vertical coverage.

    Args:
        tmp_path: Pytest-managed temporary directory for report fixtures and outputs.
    """
    output_root = tmp_path / "docs" / "images" / "generated"
    output_root.mkdir(parents=True)
    progress = output_root / "gui-progress.log"
    metrics = {
        "hem_z": 920.0,
        "shoulder_z": 1347.5,
        "target_height": 1750.0,
        "panels": [
            {
                "panel": "Drape: VisualTunicFront",
                "bounds": [-311.1, 283.3, -60.5, 182.8, 663.1575, 1235.4524],
                "diagnostics": ["below-hem-candidate"],
                "penetrating_vertices": 0,
                "target_vertex_clearance": 4.2358,
                "state": "structurally-plausible",
            },
            {
                "panel": "Drape: VisualTunicBack",
                "bounds": [-309.1, 286.6, -163.8, 59.8, 663.6136, 1235.4589],
                "diagnostics": ["below-hem-candidate"],
                "penetrating_vertices": 0,
                "target_vertex_clearance": 4.8229,
                "state": "structurally-plausible",
            },
        ],
    }
    (output_root / "drape-visual-metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    progress.write_text(
        "script-start\\ntunic-simulation-start\\n"
        "drape-metrics="
        + json.dumps(metrics["panels"][0])
        + "\\nscenario-pass\\nscript-end exit-code=0\\n",
        encoding="utf-8",
    )

    report = write_report(progress, output_root, tmp_path)

    status = _expect_dict(report["status"], message="Report status must be a dictionary.")
    fit_assessment = _expect_dict(
        report["fit_assessment"],
        message="Fit assessment must be a dictionary.",
    )
    require(
        condition=status["result"] == "review_required",
        message="Poor garment coverage must require fit review.",
    )
    require(
        condition=status["failed_stage"] is None,
        message="Successful and incomplete reports must not invent a failed stage.",
    )
    require(
        condition=fit_assessment["state"] == "review_required",
        message="Fit assessment must request review for inadequate coverage.",
    )
    observed = _expect_dict(
        fit_assessment["observed_final_panel_z_mm"],
        message="Observed final panel bounds must be a dictionary.",
    )
    deviations = _expect_dict(
        fit_assessment["deviations_mm"],
        message="Fit deviations must be a dictionary.",
    )
    require(
        condition=abs(_float_value(observed["minimum"]) - 663.158) < 0.001,
        message="The minimum final-panel height must match the regression fixture.",
    )
    require(
        condition=abs(_float_value(observed["maximum"]) - 1235.459) < 0.001,
        message="The maximum final-panel height must match the regression fixture.",
    )
    top_deviation = _float_value(deviations["cloth_top_below_shoulder_reference"])
    hem_deviation = _float_value(deviations["cloth_extends_below_expected_hem"])
    require(
        condition=abs(top_deviation - 112.041) < 0.001,
        message="The report must quantify cloth-top distance from its shoulder reference.",
    )
    require(
        condition=abs(hem_deviation - 256.842) < 0.001,
        message="The report must quantify extension below the hem reference.",
    )
    findings = _expect_list(
        fit_assessment["findings"],
        message="Fit findings must be a list.",
    )
    finding_kinds: set[str] = set()
    for finding in findings:
        finding_record = _expect_dict(finding, message="Each fit finding must be a dictionary.")
        kind = finding_record.get("kind")
        require(
            condition=isinstance(kind, str),
            message="Each fit finding must expose a string kind.",
        )
        finding_kinds.add(str(kind))
    require(
        condition=finding_kinds
        == {
            "cloth_top_below_shoulder_reference",
            "cloth_extends_below_expected_hem",
        },
        message="The fit review must identify both vertical-coverage findings.",
    )
    markdown = (output_root / "scene-understanding.md").read_text(encoding="utf-8")
    require(
        condition="## Fit and placement assessment" in markdown,
        message="Scene report predicate failed: '## Fit and placement assessment' in markd.",
    )
    require(
        condition="REVIEW REQUIRED" in markdown,
        message="The markdown report must show that fit review is required.",
    )
    require(
        condition="not an anatomical landmark" in markdown,
        message="The fit report must qualify its reference landmark.",
    )
    svg = (output_root / "scene-understanding.svg").read_text(encoding="utf-8")
    require(
        condition="Scene report result: REVIEW_REQUIRED" in svg,
        message="The SVG must render the review-required result.",
    )


def test_scene_report_preserves_sampled_native_curve_points(tmp_path: Path) -> None:
    """Retain every sampled native curve point rather than connecting only endpoints.

    Args:
        tmp_path: Pytest-managed temporary directory for report fixtures and outputs.
    """
    output_root = tmp_path / "docs" / "images" / "generated"
    output_root.mkdir(parents=True)
    boundaries = (
        ("sample-piece:edge:0", "line", 2, (0.0, 0.0), (0.0, 10.0), ((0.0, 0.0), (0.0, 10.0))),
        (
            "sample-piece:edge:1",
            "arc",
            4,
            (0.0, 10.0),
            (10.0, 10.0),
            ((0.0, 10.0), (3.0, 12.0), (7.0, 12.0), (10.0, 10.0)),
        ),
        ("sample-piece:edge:2", "line", 2, (10.0, 10.0), (0.0, 0.0), ((10.0, 10.0), (0.0, 0.0))),
    )
    progress = output_root / "gui-progress.log"
    progress.write_text(
        "tunic-outline-topology piece=Sampled ir-valid=True ir-reason=Valid Geometry "
        "draft-valid=True draft-reason=Valid Geometry ir-points=6 draft-points=3 "
        f"boundary-order={boundaries!r} near-crossing=()\n"
        "scenario-pass\n",
        encoding="utf-8",
    )

    report = write_report(progress, output_root, tmp_path)

    pattern = _expect_dict(report["pattern"], message="Pattern report must be a dictionary.")
    pieces = _expect_list(pattern["pieces"], message="Pattern pieces must be a list.")
    require(
        condition=len(pieces) == 1,
        message="Scene report predicate failed: len(pieces) == 1.",
    )
    piece = _expect_dict(pieces[0], message="Each pattern piece must be a dictionary.")
    boundary_order = _expect_list(
        piece["boundary_order"],
        message="Pattern boundary order must be a list.",
    )
    arc = _expect_dict(boundary_order[1], message="The sampled arc must be a dictionary.")
    require(
        condition=arc["samples_local_mm"] == [[0.0, 10.0], [3.0, 12.0], [7.0, 12.0], [10.0, 10.0]],
        message="The report must retain sampled native curve points.",
    )
    svg = (output_root / "scene-understanding.svg").read_text(encoding="utf-8")
    require(
        condition="36.100,591.600" in svg,
        message="The SVG must render the sampled arc geometry.",
    )


def test_scene_report_distinguishes_derived_outline_failure(tmp_path: Path) -> None:
    """Distinguish an invalid derived outline from invalid native topology.

    Args:
        tmp_path: Pytest-managed temporary directory for report fixtures and outputs.
    """
    output_root = tmp_path / "docs" / "images" / "generated"
    output_root.mkdir(parents=True)
    boundaries = (
        ("derived-piece:edge:0", "line", 2, (0.0, 0.0), (1.0, 0.0)),
        ("derived-piece:edge:1", "line", 2, (1.0, 0.0), (0.0, 1.0)),
        ("derived-piece:edge:2", "line", 2, (0.0, 1.0), (0.0, 0.0)),
    )
    nearby = ((0.0, 1, "derived-piece:edge:1", (1.0, 0.0), (0.0, 1.0)),)
    progress = output_root / "gui-progress.log"
    progress.write_text(
        "tunic-outline-topology piece=Derived ir-valid=True ir-reason=Valid Geometry "
        "draft-valid=False draft-reason=Self-intersection[0.5 0.5] ir-points=3 draft-points=3 "
        f"boundary-order={boundaries!r} near-crossing={nearby!r}\n"
        "scenario-fail exception=RuntimeError('derived pattern outline is invalid')\n",
        encoding="utf-8",
    )

    report = write_report(progress, output_root, tmp_path)

    status = _expect_dict(report["status"], message="Report status must be a dictionary.")
    stages = _expect_dict(report["stages"], message="Report stages must be a dictionary.")
    require(
        condition=status["result"] == "blocked",
        message="Invalid topology must produce a blocked report.",
    )
    require(
        condition=status["failed_stage"] == "pattern_representation",
        message="Invalid derived outline must identify the failed stage.",
    )
    require(
        condition=stages["pattern_topology"] == "valid",
        message="A valid native pattern must remain valid in the stage summary.",
    )
    require(
        condition=stages["derived_pattern_representation"] == "invalid",
        message="Invalid derived outline must be recorded in the stage summary.",
    )
    require(
        condition=stages["simulation"] == "not_reached",
        message="Simulation must not be reported as reached after a topology blocker.",
    )
    issues = _expect_list(report["issues"], message="Report issues must be a list.")
    issue = _expect_dict(issues[0], message="Each report issue must be a dictionary.")
    require(
        condition=issue["kind"] == "invalid_derived_outline",
        message="The issue kind must identify an invalid derived outline.",
    )
    require(
        condition=issue["source"] == "derived DraftingBoundary representation",
        message="The issue must identify the derived outline as its source.",
    )
