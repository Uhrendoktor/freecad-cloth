import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PatternSketchAdapter import (
    EdgeReferenceInvalid,
    build_edge_map,
    make_edge_ids,
    resolve_edge,
    validate_reference_set,
)


def test_new_piece_gets_deterministic_semantic_edge_ids():
    assert make_edge_ids("front", 4) == [
        "front:edge:0",
        "front:edge:1",
        "front:edge:2",
        "front:edge:3",
    ]


def test_semantic_id_resolves_to_current_geometry_index():
    ids = make_edge_ids("front", 4)
    assert resolve_edge(ids, 4, "front:edge:2").index == 2


def test_dimension_edit_with_same_topology_preserves_reference():
    ids = make_edge_ids("front", 4)
    before = resolve_edge(ids, 4, "front:edge:1")
    after = resolve_edge(ids, 4, "front:edge:1")
    assert before == after


def test_topology_change_is_conservatively_invalidated():
    ids = make_edge_ids("front", 4)
    try:
        build_edge_map(ids, 5)
    except EdgeReferenceInvalid as exc:
        assert "topology changed" in str(exc)
    else:
        raise AssertionError("changed geometry cardinality must invalidate references")


def test_unknown_semantic_id_never_silently_retargets():
    ids = make_edge_ids("front", 4)
    try:
        resolve_edge(ids, 4, "front:edge:99")
    except EdgeReferenceInvalid:
        return
    raise AssertionError("unknown semantic edge must remain unresolved")


def test_duplicate_ids_are_rejected():
    try:
        build_edge_map(["front:edge:0", "front:edge:0"], 2)
    except EdgeReferenceInvalid:
        return
    raise AssertionError("duplicate semantic IDs must be rejected")


def test_all_seam_references_can_be_validated_together():
    ids = make_edge_ids("front", 4)
    validate_reference_set(ids, 4, ["front:edge:0", "front:edge:3"])


def test_fake_sketch_can_use_the_same_contract_without_freecad():
    class FakeSketch:
        Geometry = [object(), object(), object()]
        SemanticEdgeIds = make_edge_ids("sleeve", 3)

    from PatternSketchAdapter import resolve_sketch_edge

    assert resolve_sketch_edge(FakeSketch(), "sleeve:edge:2").index == 2
