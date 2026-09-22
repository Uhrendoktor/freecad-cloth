from types import SimpleNamespace

import pytest

from freecad_cloth.pattern.PatternObjects import _edge_records, _resolve_document_edge
from freecad_cloth.sewing.SeamReference import ChangedEdgeReference, MissingEdgeReference, capture_edge_reference


def _piece(points=((0, 0), (10, 0), (10, 10), (0, 10))):
    return SimpleNamespace(PieceId="front", SewingOutline=repr(points))


def test_pattern_edges_have_persistent_semantic_ids():
    records = _edge_records(_piece())
    assert [record["id"] for record in records] == [
        "front:edge:0",
        "front:edge:1",
        "front:edge:2",
        "front:edge:3",
    ]
    assert records[0]["ordinal"] == 0


def test_document_edge_resolution_rejects_geometry_change():
    piece = _piece()
    record = _edge_records(piece)[0]
    reference = capture_edge_reference(piece.PieceId, record["id"], record["points"])
    assert _resolve_document_edge(piece, reference.edge_id, reference.signature)["id"] == reference.edge_id
    changed = _piece(((0, 0), (12, 0), (10, 10), (0, 10)))
    with pytest.raises(ChangedEdgeReference):
        _resolve_document_edge(changed, reference.edge_id, reference.signature)


def test_document_edge_resolution_rejects_missing_semantic_id():
    piece = _piece()
    with pytest.raises(MissingEdgeReference):
        _resolve_document_edge(piece, "front:edge:99", "deadbeef")


class _Point:
    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)
        self.z = 0.0


class _LineSegment:
    def __init__(self, start, end):
        self.StartPoint = _Point(*start)
        self.EndPoint = _Point(*end)


class _ShuffledSketch:
    Geometry = (
        _LineSegment((0, 0), (10, 0)),   # authored edge 0
        _LineSegment((0, 10), (0, 0)),   # authored edge 1
        _LineSegment((10, 0), (10, 10)), # authored edge 2
        _LineSegment((10, 10), (0, 10)), # authored edge 3
    )
    SemanticEdgeIds = (
        "piece:edge:0",
        "piece:edge:1",
        "piece:edge:2",
        "piece:edge:3",
    )

    @staticmethod
    def getConstruction(_index):
        return False


class _NativePiece:
    PieceId = "piece"
    Label = "piece"
    Width = 10.0
    Height = 10.0
    SeamAllowance = 0.0
    GrainlineAngle = 0.0
    GeometryAuthority = "Sketcher"
    DraftingBoundary = repr([(0, 0), (10, 0), (10, 10), (0, 10)])
    Sketch = _ShuffledSketch()


def test_sketcher_integer_seam_reference_uses_original_geometry_index():
    from freecad_cloth.pattern.PatternObjects import _edge_records, _seam_edge_id

    piece = _NativePiece()
    records = _edge_records(piece)
    assert [record["id"] for record in records] != [
        "piece:edge:0",
        "piece:edge:1",
        "piece:edge:2",
        "piece:edge:3",
    ]
    assert _seam_edge_id(piece, 1, "A")[0] == "piece:edge:1"
    assert _seam_edge_id(piece, 2, "A")[0] == "piece:edge:2"
    assert {record["ordinal"] for record in records} == {0, 1, 2, 3}
