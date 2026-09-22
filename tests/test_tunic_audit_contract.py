from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_tunic_uses_validated_shoulder_edge_mapping():
    source = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    assert '((1,1,"TunicRightSide"),(2,2,"TunicRightShoulder"),(6,6,"TunicLeftShoulder"),(7,7,"TunicLeftSide"))' in source
    assert '((1,1,"TunicRightSide"),(3,3,"TunicRightShoulder"),(5,5,"TunicLeftShoulder"),(7,7,"TunicLeftSide"))' not in source

def test_canonical_tunic_uses_native_sketch_semantic_seam_ids():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert 'front_edge_ids = tuple(str(edge_id) for edge_id in getattr(front.Sketch, "SemanticEdgeIds", ()))' in source
    assert 'back_edge_ids = tuple(str(edge_id) for edge_id in getattr(back.Sketch, "SemanticEdgeIds", ()))' in source
    assert 'semantic_edge_a = front_edge_ids[int(edge_a)]' in source
    assert 'semantic_edge_b = back_edge_ids[int(edge_b)]' in source
    assert 'Seam(str(front.PieceId), semantic_edge_a, str(back.PieceId), semantic_edge_b' in source
    assert 'Seam(str(front.PieceId), edge_a, str(back.PieceId), edge_b' not in source
    assert 'canonical tunic seam did not retain Sketcher semantic edge provenance' in source


def test_canonical_tunic_pins_only_one_side_of_sewn_shoulders():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert "scene.PinSelection = [str(i) for i in front_pins]" in source
    assert "scene.PinSelection = [str(i) for i in front_pins + back_pins]" not in source
    assert "the back panel must follow through the" in source

def test_canonical_tunic_rejects_known_shoulder_mapping_regressions():
    audit = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    assert '((1,1,"TunicRightSide"),(2,2,"TunicRightShoulder"),(6,6,"TunicLeftShoulder"),(7,7,"TunicLeftSide"))' in audit
    assert '((1,1,"TunicRightSide"),(3,3,"TunicRightShoulder"),(5,5,"TunicLeftShoulder"),(7,7,"TunicLeftSide"))' not in audit
    assert '((1,1,"TunicRightSide"),(2,2,"TunicRightShoulder"),(5,5,"TunicLeftShoulder"),(7,7,"TunicLeftSide"))' not in audit
    assert '((1,1,"TunicRightSide"),(3,3,"TunicRightShoulder"),(6,6,"TunicLeftShoulder"),(7,7,"TunicLeftSide"))' not in audit
