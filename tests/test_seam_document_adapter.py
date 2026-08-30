from types import SimpleNamespace

import pytest

from PatternObjects import _edge_records, _resolve_document_edge
from SeamReference import ChangedEdgeReference, MissingEdgeReference, capture_edge_reference


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
        self.x = x
        self.y = y


class _Line:
    def __init__(self, start, end):
        self.StartPoint = _Point(*start)
        self.EndPoint = _Point(*end)


class _Sketch:
    def __init__(self, geometry, semantic_ids=None, construction=()):
        self.Geometry = geometry
        self.SemanticEdgeIds = semantic_ids or ()
        self._construction = set(construction)

    def getConstruction(self, index):
        return index in self._construction


def test_sketcher_geometry_is_authoritative_for_seam_references():
    sketch = _Sketch(
        [_Line((0, 0), (10, 0)), _Line((10, 0), (10, 10)), _Line((10, 10), (0, 10))],
        ("front:edge:0", "front:edge:1", "front:edge:2"),
    )
    piece = SimpleNamespace(PieceId="front", SewingOutline=repr(((0, 0), (1, 0), (1, 1))), Sketch=sketch)
    records = _edge_records(piece)
    assert [record["id"] for record in records] == ["front:edge:0", "front:edge:1", "front:edge:2"]
    assert records[0]["points"] == ((0.0, 0.0), (10.0, 0.0))
    assert records[1]["points"] == ((10.0, 0.0), (10.0, 10.0))

    reference = capture_edge_reference("front", "front:edge:0", records[0]["points"])
    sketch.Geometry[0] = _Line((0, 0), (12, 0))
    with pytest.raises(ChangedEdgeReference):
        _resolve_document_edge(piece, reference.edge_id, reference.signature)


def test_sketcher_construction_geometry_is_not_a_seam_edge():
    sketch = _Sketch(
        [_Line((0, 0), (10, 0)), _Line((0, 0), (0, 10)), _Line((10, 0), (10, 10))],
        ("front:edge:0", "front:construction", "front:edge:1"),
        construction=(1,),
    )
    piece = SimpleNamespace(PieceId="front", SewingOutline="", Sketch=sketch)
    records = _edge_records(piece)
    assert [record["id"] for record in records] == ["front:edge:0", "front:edge:1"]
