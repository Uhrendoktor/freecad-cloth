"""Contracts for the published README visual validation path."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_readme_turntable_uses_real_blanket_drape_motion():
    source = (ROOT / "tests" / "freecad_simulation_turntable.py").read_text(encoding="utf-8")
    assert 'Part::Box' in source
    assert 'BlanketSource' in source
    assert 'ClothPieces = [blanket]' in source
    assert 'blanket-motion-diagnostic' in source
    assert 'blanket-turntable-pass' in source
    assert 'if displacement < 40.0' in source
    assert 'minimum_z > cube_top + 35.0' in source


def test_readme_turntable_uses_exact_drape_target_mesh():
    source = (ROOT / "tests" / "freecad_simulation_turntable.py").read_text(encoding="utf-8")
    assert 'create_drape_target(doc, cube, "FreeCAD Geometry"' in source
    assert 'assign_drape_target(target, cube, "FreeCAD Geometry")' in source
    assert 'DrapeTarget' in source


def test_canonical_workflow_fails_closed_on_turntable_quality():
    source = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
    assert "CLOTH_TISSU_SUBSTEPS: 10" in source
    assert "CLOTH_TISSU_COLLISION_MODE: mesh" in source
    assert "blanket-motion-diagnostic" in source
    assert "blanket-turntable-pass" in source
    assert 'test "$(find docs/images/generated/cloth-simulation-draped-turntable-frames' in source
    assert 'checkpoint-uniqueness=passed' in source


def test_blanket_motion_gif_delay_is_applied_before_inputs_and_checked():
    source = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
    input_glob = "docs/images/generated/blanket-example/motion-*.png"
    encode_options = '"${IM[@]}" -delay 10 -loop 0 -colors 128'
    assert encode_options in source
    assert source.index(encode_options) < source.index(input_glob)
    assert 'frame_delays=''$(identify -format '%T\\n' docs/images/generated/blanket-example/blanket-motion.gif | sort -u)'' in source
    assert 'test "$frame_delays" = "10"' in source