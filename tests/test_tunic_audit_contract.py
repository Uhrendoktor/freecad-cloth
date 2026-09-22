from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_tunic_uses_authored_sketch_semantic_edge_ids():
    source = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    assert 'getattr(sketch, "SemanticEdgeIds", ())' in source
    assert 'front_semantic_edge_ids = {index: _semantic_edge_id(front.Sketch, index) for index in (1, 2, 6, 7)}' in source
    assert 'back_semantic_edge_ids = {index: _semantic_edge_id(back.Sketch, index) for index in (1, 2, 6, 7)}' in source
    assert 'for authored_a, authored_b, seam_id in ((1, 1, "TunicRightSide"), (2, 2, "TunicRightShoulder"), (6, 6, "TunicLeftShoulder"), (7, 7, "TunicLeftSide")):' in source
    assert 'Seam(str(front.PieceId), edge_a, str(back.PieceId), edge_b' in source
    assert 'Seam(str(front.PieceId), authored_a, str(back.PieceId), authored_b' not in source
    assert 'canonical tunic seam %s did not retain authored semantic edge IDs' in source
    assert 'tunic-seam-map=' in source
    assert 'edge_a = int(seam.EdgeA)' not in source

def test_canonical_tunic_pins_only_one_side_of_sewn_shoulders():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert "scene.PinSelection = [str(i) for i in front_pins]" in source
    assert "scene.PinSelection = [str(i) for i in front_pins + back_pins]" not in source
    assert "the back panel must follow through the" in source

def test_canonical_tunic_rejects_known_shoulder_mapping_regressions():
    audit = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    assert '(1, 1, "TunicRightSide")' in audit
    assert '(2, 2, "TunicRightShoulder")' in audit
    assert '(6, 6, "TunicLeftShoulder")' in audit
    assert '(7, 7, "TunicLeftSide")' in audit
    assert '(3, 3, "TunicRightShoulder")' not in audit
    assert '(5, 5, "TunicLeftShoulder")' not in audit
