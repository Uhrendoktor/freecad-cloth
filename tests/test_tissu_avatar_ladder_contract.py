"""Contract tests for the diagnostic avatar complexity ladder."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "tests" / "freecad_tissu_avatar_ladder.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")


def test_avatar_ladder_contract_is_diagnostic_only_and_frozen():
    for case_id in (
        "rung-6-avatar-pinned",
        "rung-7-avatar-unpinned",
        "rung-8-avatar-two-piece-no-seam",
        "rung-9-avatar-two-piece-small-seam",
        "rung-10-avatar-two-piece-large-seam",
    ):
        assert case_id in SOURCE

    assert "CHECKPOINTS = (0, 1, 5, 15, 45, 90)" in SOURCE
    assert '"diagnostic-only-avatar-complexity-ladder"' in SOURCE
    assert '"release_gate_effect": "none"' in SOURCE
    assert '"target": "avatar"' in SOURCE
    assert '"AvatarType", ""' in SOURCE
    assert '"ClothAvatar"' in SOURCE
    assert '"DrapeTarget"' in SOURCE
    assert '"ArrangementPoints"' in SOURCE
    assert '"shoulder_left"' in SOURCE
    assert '"hip"' in SOURCE
    assert "solver_collision_surface" in SOURCE
    assert '"source_triangles"' in SOURCE
    assert '"solver_triangles"' in SOURCE
    assert '"seam_world_spans_mm"' in SOURCE
    assert '"placement_offsets_mm"' in SOURCE
    assert "first_failing_rung" in SOURCE
    assert "QtCore.QTimer.singleShot(0, _run_and_shutdown)" in SOURCE
    assert "Run avatar complexity ladder" in WORKFLOW
    assert "Validate avatar ladder artifact" in WORKFLOW
    assert "avatar-ladder-2482" in WORKFLOW
