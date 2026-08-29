import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from SeamReference import (
    ChangedEdgeReference,
    EdgeReference,
    MissingEdgeReference,
    capture_edge_reference,
    edge_signature,
    resolve_edge_reference,
    resolve_edge_reference_status,
    semantic_edge_id,
)


def _edge(piece_id="front", edge_id="front:edge:2", points=((0, 0), (10, 0))):
    return {"piece_id": piece_id, "id": edge_id, "points": points, "ordinal": 2}


def test_semantic_edge_id_is_deterministic():
    assert semantic_edge_id("front", 2) == "front:edge:2"
    assert semantic_edge_id("front", "2") == "front:edge:2"


def test_signature_is_deterministic_and_order_sensitive():
    points = ((0, 0), (5, 2), (10, 0))
    assert edge_signature(points) == edge_signature(points)
    assert edge_signature(points) != edge_signature(tuple(reversed(points)))


def test_reference_round_trips_as_document_data():
    reference = capture_edge_reference("front", "front:edge:2", ((0, 0), (10, 0)))
    restored = EdgeReference.from_dict(reference.as_dict())
    assert restored == reference


def test_resolver_uses_semantic_id_not_ordinal():
    reference = capture_edge_reference("front", "front:edge:2", ((0, 0), (10, 0)))
    edges = [
        _edge("front", "front:edge:7", ((0, 0), (10, 0))),
        _edge("front", "front:edge:2", ((0, 0), (10, 0))),
    ]
    assert resolve_edge_reference(reference, edges)["id"] == "front:edge:2"


def test_missing_semantic_id_is_explicitly_invalid():
    reference = capture_edge_reference("front", "front:edge:2", ((0, 0), (10, 0)))
    with pytest.raises(MissingEdgeReference):
        resolve_edge_reference(reference, [_edge("front", "front:edge:7")])
    assert resolve_edge_reference_status(reference, [_edge("front", "front:edge:7")]) == (False, "missing")


def test_changed_geometry_never_retargets_reference():
    reference = capture_edge_reference("front", "front:edge:2", ((0, 0), (10, 0)))
    changed = [_edge("front", "front:edge:2", ((0, 0), (12, 0)))]
    with pytest.raises(ChangedEdgeReference):
        resolve_edge_reference(reference, changed)
    assert resolve_edge_reference_status(reference, changed) == (False, "changed")


def test_other_piece_with_same_edge_id_does_not_match():
    reference = capture_edge_reference("front", "front:edge:2", ((0, 0), (10, 0)))
    with pytest.raises(MissingEdgeReference):
        resolve_edge_reference(reference, [_edge("back", "front:edge:2")])


def test_invalid_reference_inputs_fail_early():
    with pytest.raises(ValueError):
        EdgeReference("", "front:edge:0", "abc")
    with pytest.raises(ValueError):
        EdgeReference("front", "", "abc")
    with pytest.raises(ValueError):
        edge_signature(((0, 0),))
