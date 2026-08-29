import pytest

from PatternSemanticRefs import (
    EdgeResolution,
    SemanticEdgeRef,
    migrate_index_reference,
    resolve_edge,
    semantic_edge_ids,
    validate_unique_edge_ids,
)


def test_initial_ids_are_deterministic():
    assert semantic_edge_ids("front", 3) == (
        "front:edge:0",
        "front:edge:1",
        "front:edge:2",
    )


def test_reference_round_trips():
    ref = SemanticEdgeRef.from_index("front", 4)
    assert ref.key == "front:edge:4"
    assert SemanticEdgeRef.parse(ref.key) == ref


def test_resolution_returns_current_geometry_index():
    ids = ("front:edge:4", "front:edge:9")
    result = resolve_edge(SemanticEdgeRef.parse("front:edge:9"), ids)
    assert result == EdgeResolution(SemanticEdgeRef.parse("front:edge:9"), 1, True)


def test_missing_reference_is_invalid_not_retargeted():
    ref = SemanticEdgeRef.parse("front:edge:9")
    result = resolve_edge(ref, ("front:edge:0", "front:edge:1"))
    assert not result.valid
    assert result.geometry_index is None
    assert "no longer exists" in result.reason


def test_duplicate_ids_are_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        validate_unique_edge_ids(("front:edge:0", "front:edge:0"))


def test_legacy_index_migration_requires_matching_semantic_id():
    assert migrate_index_reference("front", 1, ("front:edge:0", "front:edge:1")) == SemanticEdgeRef.from_index("front", 1)
    with pytest.raises(ValueError, match="cannot be resolved"):
        migrate_index_reference("front", 2, ("front:edge:0", "front:edge:1"))


def test_invalid_reference_syntax_is_rejected():
    with pytest.raises(ValueError):
        SemanticEdgeRef.parse("Edge3")
