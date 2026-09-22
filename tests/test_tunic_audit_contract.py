from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_tunic_uses_validated_shoulder_edge_mapping():
    source = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    assert 'authored_edge_ids = tuple(str(value) for value in getattr(front.Sketch, "SemanticEdgeIds", ()) or ())' in source
    assert '((1,1,"TunicRightSide"),(3,3,"TunicRightShoulder"),(5,5,"TunicLeftShoulder"),(7,7,"TunicLeftSide"))' not in source

def test_canonical_tunic_pins_only_one_side_of_sewn_shoulders():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert "scene.PinSelection = [str(i) for i in front_pins]" in source
    assert "scene.PinSelection = [str(i) for i in front_pins + back_pins]" not in source
    assert "the back panel must follow through the" in source

def test_canonical_tunic_rejects_known_shoulder_mapping_regressions():
    audit = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    assert 'authored_edge_ids = tuple(str(value) for value in getattr(front.Sketch, "SemanticEdgeIds", ()) or ())' in audit
    assert '((1,1,"TunicRightSide"),(3,3,"TunicRightShoulder"),(5,5,"TunicLeftShoulder"),(7,7,"TunicLeftSide"))' not in audit
    assert '((1,1,"TunicRightSide"),(2,2,"TunicRightShoulder"),(5,5,"TunicLeftShoulder"),(7,7,"TunicLeftSide"))' not in audit
    assert '((1,1,"TunicRightSide"),(3,3,"TunicRightShoulder"),(6,6,"TunicLeftShoulder"),(7,7,"TunicLeftSide"))' not in audit


def test_sketch_authority_integer_edge_uses_native_semantic_id():
    from types import SimpleNamespace
    from freecad_cloth.pattern.PatternObjects import _seam_edge_id

    class Point:
        def __init__(self, x, y):
            self.x, self.y, self.z = x, y, 0.0

    class Line:
        def __init__(self, start, end):
            self.StartPoint = Point(*start)
            self.EndPoint = Point(*end)

    class Sketch:
        Geometry = [
            Line((0, 0), (10, 0)), Line((10, 0), (10, 8)),
            Line((10, 8), (8, 10)), Line((8, 10), (2, 10)),
            Line((2, 10), (0, 8)), Line((0, 8), (0, 10)),
            Line((0, 10), (-2, 8)), Line((-2, 8), (0, 0)),
        ]
        SemanticEdgeIds = [f"front:edge:{index}" for index in range(8)]

    piece = SimpleNamespace(PieceId="front", GeometryAuthority="Sketcher", Sketch=Sketch())
    semantic_id, _ = _seam_edge_id(piece, 1, "A")
    assert semantic_id == "front:edge:1"
