from types import SimpleNamespace

import pytest

from freecad_cloth.pattern.PatternObjects import _edge_records, _resolve_document_edge
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
