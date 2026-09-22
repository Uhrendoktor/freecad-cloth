from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_tunic_uses_semantic_edge_ids_for_all_authored_seams():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert '(front_edge_ids[1], back_edge_ids[1], "TunicRightSide")' in source
    assert '(front_edge_ids[2], back_edge_ids[2], "TunicRightShoulder")' in source
    assert '(front_edge_ids[6], back_edge_ids[6], "TunicLeftShoulder")' in source
    assert '(front_edge_ids[7], back_edge_ids[7], "TunicLeftSide")' in source
    assert 'Seam(str(front.PieceId), edge_a, str(back.PieceId), edge_b' in source

def test_canonical_tunic_pins_only_one_side_of_sewn_shoulders():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert "scene.PinSelection = [str(i) for i in front_pins]" in source
    assert "scene.PinSelection = [str(i) for i in front_pins + back_pins]" not in source
    assert "the back panel must follow through the" in source

def test_tunic_seam_audit_uses_persisted_semantic_edge_ids():
    audit = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    assert 'edge_a_id = str(getattr(seam, "EdgeAId", "")).strip()' in audit
    assert 'edge_b_id = str(getattr(seam, "EdgeBId", "")).strip()' in audit
    assert 'resolve_piece_ir(piece)' in audit
    assert 'getattr(seam, "EdgeA", 0)' not in audit
    assert 'getattr(seam, "EdgeB", 0)' not in audit
