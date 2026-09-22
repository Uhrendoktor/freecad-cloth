from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_tunic_uses_independent_front_back_semantic_edge_ids():
    source = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    assert 'front_edge_ids = tuple(str(value) for value in getattr(front.Sketch, "SemanticEdgeIds", ()) or ())' in source
    assert 'back_edge_ids = tuple(str(value) for value in getattr(back.Sketch, "SemanticEdgeIds", ()) or ())' in source
    assert 'front_edge_ids[1], back_edge_ids[1], "TunicRightSide"' in source
    assert 'front_edge_ids[2], back_edge_ids[2], "TunicRightShoulder"' in source
    assert 'front_edge_ids[6], back_edge_ids[6], "TunicLeftShoulder"' in source
    assert 'front_edge_ids[7], back_edge_ids[7], "TunicLeftSide"' in source
    assert 'f"{front.PieceId}:edge:1", f"{back.PieceId}:edge:1"' not in source

def test_canonical_tunic_pins_only_one_side_of_sewn_shoulders():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert "scene.PinSelection = [str(i) for i in front_pins]" in source
    assert "scene.PinSelection = [str(i) for i in front_pins + back_pins]" not in source
    assert "the back panel must follow through the" in source

def test_canonical_tunic_rejects_integer_seam_mapping_regression():
    audit = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    assert 'f"{front.PieceId}:edge:1", f"{back.PieceId}:edge:1", "TunicRightSide"' in audit
    assert 'f"{front.PieceId}:edge:2", f"{back.PieceId}:edge:2", "TunicRightShoulder"' in audit
    assert 'f"{front.PieceId}:edge:5", f"{back.PieceId}:edge:5", "TunicLeftShoulder"' in audit
    assert 'f"{front.PieceId}:edge:6", f"{back.PieceId}:edge:6", "TunicLeftSide"' in audit
    assert '(1,1,"TunicRightSide")' not in audit
