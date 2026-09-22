from types import SimpleNamespace

from freecad_cloth.pattern.PatternObjects import _native_edge_record_for_sketch_index, _seam_edge_id
from freecad_cloth.sewing.SeamReference import capture_edge_reference


class _Point:
    def __init__(self, x, y):
        self.x, self.y, self.z = x, y, 0.0


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


def test_native_edge_number_maps_to_authored_semantic_edge_after_patternir_reordering():
    piece = SimpleNamespace(PieceId="front", GeometryAuthority="Sketcher", Sketch=_Sketch())
    original = __import__("freecad_cloth.pattern.PatternObjects", fromlist=["_native_edge_records"])._native_edge_records
    records = tuple(
        {"id": f"front:edge:{index}", "points": ((float(index), 0.0), (float(index + 1), 0.0)),
         "provenance": ("PatternIR", "Sketcher", "line", (0.0, 1.0), ((float(index), 0.0, 0.0), (float(index + 1), 0.0, 0.0)))}
        for index in (0, 7, 6, 5, 4, 3, 2, 1)
    )
    module = __import__("freecad_cloth.pattern.PatternObjects", fromlist=["_native_edge_records"])
    module._native_edge_records = lambda _piece: records
    try:
        semantic_id, signature = _seam_edge_id(piece, 5, "A")
    finally:
        module._native_edge_records = original
    assert semantic_id == "front:edge:5"
    expected = capture_edge_reference("front", "front:edge:5", ((5.0, 0.0), (6.0, 0.0)), records[3]["provenance"]).signature
    assert signature == expected


def test_native_sketch_missing_semantic_edge_fails_closed():
    piece = SimpleNamespace(PieceId="front", GeometryAuthority="Sketcher", Sketch=SimpleNamespace(SemanticEdgeIds=["front:edge:0"]))
    try:
        _native_edge_record_for_sketch_index(piece, 1)
    except Exception as exc:
        assert "native Sketcher seam edge 1" in str(exc)
        return
    raise AssertionError("missing native semantic edge must fail closed")
