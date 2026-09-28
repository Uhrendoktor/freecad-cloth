from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_cube_ladder_contract_is_diagnostic_only_and_frozen():
    source = (ROOT / "tests" / "freecad_tissu_cube_ladder.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")

    for case_id in (
        "rung-1-cube-pinned",
        "rung-2-cube-unpinned",
        "rung-3-cube-two-piece-no-seam",
        "rung-4-cube-two-piece-small-seam",
        "rung-5-cube-two-piece-large-seam",
    ):
        assert case_id in source

    assert "CHECKPOINTS = (0, 1, 5, 15, 45, 90)" in source
    assert '"diagnostic-only-cube-complexity-ladder"' in source
    assert '"release_gate_effect": "none"' in source
    assert "seam_stitch_pairs" in source
    assert "seam_world_spans_mm" in source
    assert "first_failing_rung" in source
    assert "CLOTH_CONTACT_DIAGNOSTICS_EXECUTE" in workflow
    assert "Run cube complexity ladder" in workflow
    assert "Validate cube ladder artifact" in workflow
