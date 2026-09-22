from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_tunic_uses_authored_semantic_edge_ids():
    source = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    assert 'authored_edge_ids = tuple(str(value) for value in getattr(front.Sketch, "SemanticEdgeIds", ()) or ())' in source
    assert 'authored_edge_ids[1], authored_edge_ids[1], "TunicRightSide"' in source
    assert 'authored_edge_ids[2], authored_edge_ids[2], "TunicRightShoulder"' in source
    assert 'authored_edge_ids[6], authored_edge_ids[6], "TunicLeftShoulder"' in source
    assert 'authored_edge_ids[7], authored_edge_ids[7], "TunicLeftSide"' in source
    assert '((1,1,"TunicRightSide"),(2,2,"TunicRightShoulder"),(6,6,"TunicLeftShoulder"),(7,7,"TunicLeftSide"))' not in source

def test_canonical_tunic_pins_only_one_side_of_sewn_shoulders():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert "scene.PinSelection = [str(i) for i in front_pins]" in source
    assert "scene.PinSelection = [str(i) for i in front_pins + back_pins]" not in source
    assert "the back panel must follow through the" in source

def test_canonical_tunic_rejects_known_shoulder_mapping_regressions():
    audit = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    assert 'authored_edge_ids = tuple(str(value) for value in getattr(front.Sketch, "SemanticEdgeIds", ()) or ())' in audit
    assert 'edge_a_id, edge_b_id, seam_id in ((authored_edge_ids[1], authored_edge_ids[1], "TunicRightSide")' in audit
    assert '((1,1,"TunicRightSide"),(2,2,"TunicRightShoulder"),(6,6,"TunicLeftShoulder"),(7,7,"TunicLeftSide"))' not in audit
    assert '((1,1,"TunicRightSide"),(3,3,"TunicRightShoulder"),(5,5,"TunicLeftShoulder"),(7,7,"TunicLeftSide"))' not in audit
