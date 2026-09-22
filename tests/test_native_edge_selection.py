from types import SimpleNamespace

from freecad_cloth.pattern.PatternObjects import _seam_edge_id


class _Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.z = 0.0


class _Line:
    def __init__(self, start, end):
        self.StartPoint = _Point(*start)
        self.EndPoint = _Point(*end)


class _Sketch:
    Geometry = [
        _Line((0, 0), (10, 0)),
        _Line((10, 0), (10, 8)),
        _Line((10, 8), (8, 10)),
        _Line((8, 10), (2, 10)),
        _Line((2, 10), (0, 8)),
        _Line((0, 8), (0, 10)),
        _Line((0, 10), (-2, 8)),
        _Line((-2, 8), (0, 0)),
    ]
    SemanticEdgeIds = [f"front:edge:{index}" for index in range(8)]


def test_sketch_authority_integer_edge_uses_native_semantic_id():
    piece = SimpleNamespace(
        PieceId="front",
        GeometryAuthority="Sketcher",
        Sketch=_Sketch(),
    )
    semantic_id, _signature = _seam_edge_id(piece, 1, "A")
    assert semantic_id == "front:edge:1"
