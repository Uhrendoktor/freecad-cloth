from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_tunic_uses_authored_semantic_edge_ids():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert 'front_edge_ids[1], back_edge_ids[1], "TunicRightSide"' in source
    assert 'front_edge_ids[3], back_edge_ids[3], "TunicRightShoulder"' in source
    assert 'front_edge_ids[5], back_edge_ids[5], "TunicLeftShoulder"' in source
    assert 'front_edge_ids[7], back_edge_ids[7], "TunicLeftSide"' in source
    assert 'Seam(str(front.PieceId), 2, str(back.PieceId), 2' not in source
    assert 'Seam(str(front.PieceId), 5, str(back.PieceId), 5' not in source


def test_canonical_tunic_pins_only_one_side_of_sewn_shoulders():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert "scene.PinSelection = [str(i) for i in front_pins]" in source
    assert "scene.PinSelection = [str(i) for i in front_pins + back_pins]" not in source
    assert "the back panel must follow through the" in source


def test_tunic_seam_audit_uses_persisted_semantic_edge_ids():
    audit = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    assert 'seam_check = """' in audit
    assert 'EdgeAId' in audit
    assert 'EdgeBId' in audit
    assert 'max_seam_gap > 35.0' in audit
