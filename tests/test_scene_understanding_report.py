"""Tests for artifact-only scene diagnosis and geometry annotation."""

from __future__ import annotations

import json
from pathlib import Path

from tools.ci.scene_understanding_report import write_report


def _invalid_topology_log() -> str:
    """Build the same key geometric facts found in the PR #2674 workflow artifact."""
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
    """Format a native armhole sample record."""
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
    """The report must identify topology as the blocker and refuse to claim a drape result."""
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
                "screenshot=/workspace/docs/images/generated/cloth-mannequin-near-t-pose.png state=pose bytes=13",
                "screenshot=/workspace/docs/images/generated/cloth-pattern-design.png state=pattern bytes=16",
                "screenshot=/workspace/docs/images/generated/cloth-sewing.png state=sewing bytes=14",
                "scenario-fail exception=ValueError('pattern boundary self-intersects')",
                "script-end exit-code=1",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    report = write_report(progress, output_root, workspace)

    status = report["status"]
    stages = report["stages"]
    assert isinstance(status, dict)
    assert isinstance(stages, dict)
    assert status["result"] == "blocked"
    assert status["failed_stage"] == "pattern_topology"
    assert stages["pattern_topology"] == "invalid"
    assert stages["simulation"] == "not_reached"
    assert stages["drape"] == "not_reached"
    issues = report["issues"]
    assert isinstance(issues, list) and len(issues) == 1
    issue = issues[0]
    assert isinstance(issue, dict)
    assert issue["edge_ids"] == ["pattern-piece-1:edge:3", "pattern-piece-1:edge:2"]
    assert issue["point_local_mm"] == [627.926235325921, 482.858393143538]

    written = json.loads((output_root / "scene-understanding.json").read_text(encoding="utf-8"))
    assert written["status"]["failed_stage"] == "pattern_topology"
    markdown = (output_root / "scene-understanding.md").read_text(encoding="utf-8")
    assert "do not tune collision" in markdown
    svg = (output_root / "scene-understanding.svg").read_text(encoding="utf-8")
    assert "627.926" in svg
    assert "INVALID" in svg
    assert 'stroke="#cc3333"' in svg


def test_missing_progress_log_emits_explicit_incomplete_dossier(tmp_path: Path) -> None:
    """Even an early crash should leave a report saying evidence was not observed."""
    output_root = tmp_path / "docs" / "images" / "generated"
    report = write_report(tmp_path / "missing.log", output_root, tmp_path)

    status = report["status"]
    stages = report["stages"]
    assert isinstance(status, dict)
    assert isinstance(stages, dict)
    assert status["result"] == "incomplete"
    assert status["failed_stage"] is None
    assert stages["simulation"] == "not_observed"
    assert (output_root / "scene-understanding.json").is_file()
    assert (output_root / "scene-understanding.md").is_file()
    assert (output_root / "scene-understanding.svg").is_file()


def test_success_status_does_not_invent_a_topology_failure(tmp_path: Path) -> None:
    """A successful run should retain neutral stage facts rather than inventing blockers."""
    output_root = tmp_path / "docs" / "images" / "generated"
    output_root.mkdir(parents=True)
    progress = output_root / "gui-progress.log"
    progress.write_text(
        "script-start\nscenario-pass\ntunic-audit-process-exit=success\n",
        encoding="utf-8",
    )

    report = write_report(progress, output_root, tmp_path)

    status = report["status"]
    assert isinstance(status, dict)
    assert status["result"] == "passed"
    assert status["failed_stage"] is None
    assert report["issues"] == []


def test_scene_report_preserves_sampled_native_curve_points(tmp_path: Path) -> None:
    """The dossier must retain the full native curve rather than connecting only endpoints."""
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

    pattern = report["pattern"]
    assert isinstance(pattern, dict)
    pieces = pattern["pieces"]
    assert isinstance(pieces, list) and len(pieces) == 1
    piece = pieces[0]
    assert isinstance(piece, dict)
    boundary_order = piece["boundary_order"]
    assert isinstance(boundary_order, list)
    arc = boundary_order[1]
    assert isinstance(arc, dict)
    assert arc["samples_local_mm"] == [[0.0, 10.0], [3.0, 12.0], [7.0, 12.0], [10.0, 10.0]]
    svg = (output_root / "scene-understanding.svg").read_text(encoding="utf-8")
    assert "36.100,591.600" in svg


def test_scene_report_distinguishes_derived_outline_failure(tmp_path: Path) -> None:
    """A valid native pattern must not be described as an invalid PatternIR topology."""
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

    status = report["status"]
    stages = report["stages"]
    assert isinstance(status, dict) and isinstance(stages, dict)
    assert status["result"] == "blocked"
    assert status["failed_stage"] == "pattern_representation"
    assert stages["pattern_topology"] == "valid"
    assert stages["derived_pattern_representation"] == "invalid"
    assert stages["simulation"] == "not_reached"
    issue = report["issues"][0]
    assert isinstance(issue, dict)
    assert issue["kind"] == "invalid_derived_outline"
    assert issue["source"] == "derived DraftingBoundary representation"


