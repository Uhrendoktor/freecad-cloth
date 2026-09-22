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


class _NativeSketch:
    SemanticEdgeIds = tuple(f"piece:edge:{index}" for index in range(4))


class _NativePiece:
    PieceId = "piece"
    GeometryAuthority = "Sketcher"
    Sketch = _NativeSketch()


def test_sketcher_integer_seam_reference_uses_authored_geometry_index_after_boundary_reordering():
    import freecad_cloth.pattern.PatternObjects as pattern_objects

    piece = _NativePiece()
    semantic_ids = tuple(f"piece:edge:{index}" for index in range(4))
    reordered = [
        {"id": semantic_ids[index], "points": ((float(index), 0.0), (float(index + 1), 0.0)),
         "ordinal": traversal, "provenance": ("PatternIR", "Sketcher", "line", (0.0, 1.0),
            ((float(index), 0.0, 0.0), (float(index + 1), 0.0, 0.0)))}
        for traversal, index in enumerate((0, 3, 2, 1))
    ]
    previous = pattern_objects._native_edge_records
    pattern_objects._native_edge_records = lambda _piece: reordered
    try:
        assert [record["id"] for record in _edge_records(piece)] == [
            "piece:edge:0", "piece:edge:3", "piece:edge:2", "piece:edge:1"
        ]
        assert pattern_objects._seam_edge_id(piece, 1, "A")[0] == "piece:edge:1"
        assert pattern_objects._seam_edge_id(piece, 2, "A")[0] == "piece:edge:2"
    finally:
        pattern_objects._native_edge_records = previous


def test_sketcher_semantic_seam_reference_keeps_provenance_signature():
    import freecad_cloth.pattern.PatternObjects as pattern_objects

    piece = _NativePiece()
    record = {
        "id": "piece:edge:2",
        "points": ((2.0, 0.0), (3.0, 0.0)),
        "ordinal": 0,
        "provenance": ("PatternIR", "Sketcher", "line", (0.0, 1.0),
            ((2.0, 0.0, 0.0), (3.0, 0.0, 0.0))),
    }
    previous = pattern_objects._native_edge_records
    pattern_objects._native_edge_records = lambda _piece: [record]
    try:
        edge_id, signature = pattern_objects._seam_edge_id(piece, "piece:edge:2", "A")
    finally:
        pattern_objects._native_edge_records = previous
    assert edge_id == "piece:edge:2"
    assert signature == capture_edge_reference(
        piece.PieceId, record["id"], record["points"], record["provenance"]
    ).signature
