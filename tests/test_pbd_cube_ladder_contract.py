# Copyright (C) 2026 FreeCAD Cloth contributors
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPERS = (ROOT / "tests" / "support" / "pbd_contact_helpers.py").read_text(encoding="utf-8")


def test_cube_ladder_contract_is_gate_and_frozen() -> None:
    """Require the collision ladder to remain a release gate with frozen evidence."""
    source = (ROOT / "tests" / "freecad_pbd_cube_ladder.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )

    for case_id in (
        "rung-1-cube-pinned",
        "rung-2-cube-unpinned",
        "rung-3-cube-two-piece-no-seam",
        "rung-4-cube-two-piece-small-seam",
        "rung-5-cube-two-piece-large-seam",
    ):
        assert case_id in source

    assert "LADDER_CHECKPOINTS = (0, 1, 5, 15, 45, 90)" in HELPERS
    assert 'purpose="simulation-collision-ladder"' in source
    assert '"release_gate_effect": "gate"' in HELPERS
    assert "seam_stitch_pairs" in HELPERS
    assert "seam_world_spans_mm" in HELPERS
    assert "first_failing_rung" in HELPERS
    assert "CLOTH_CONTACT_DIAGNOSTICS_EXECUTE" in workflow
    assert "runpy.run_path(" not in source
    assert "_ladder.capture_ladder_checkpoints(" in source
    assert "_ladder.build_ladder_case_record(" in source
    assert "_ladder.write_ladder_manifest(" in source
    assert '_HELPER_DIR = Path(__file__).resolve().parent / "support"' in source
    assert "_REPO_ROOT = Path(__file__).resolve().parents[1]" in source
    assert "sys.path.insert(0, str(_REPO_ROOT))" in source
    assert "sys.path.insert(0, str(_HELPER_DIR))" in source
    assert "before-support-helper-import" in source
    assert "after-support-helper-import" in source
    assert '"right_x": 20.0' in source
    # The canonical job owns the full ladder gate and uploads the frozen evidence.
    assert "simulation-ladder:" in workflow
    assert "test-script: tests/freecad_pbd_cube_ladder.py" in workflow
    assert "validate-command: python3 tools/ci/validate_manifests.py simulation" in workflow
    assert "artifact-name: simulation-collision-ladder" in workflow
