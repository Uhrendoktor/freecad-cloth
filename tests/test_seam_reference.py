# Copyright (C) 2026 FreeCAD Cloth contributors
"""Contract tests for provenance-backed semantic seam-edge references."""

import sys
from pathlib import Path
from typing import cast

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from freecad_cloth.pattern.SeamReference import (
    ChangedEdgeReference,
    EdgeReference,
    MissingEdgeReference,
    capture_edge_reference,
    edge_signature,
    resolve_edge_reference,
    resolve_edge_reference_status,
    semantic_edge_id,
)


def _provenance(points: tuple[tuple[float, float], ...]) -> tuple[object, ...]:
    """Build the same native line provenance used by a test edge record."""
    return ("PatternIR", "Sketcher", "line", (0.0, 1.0), tuple(points))


def _edge(
    piece_id: str = "front",
    edge_id: str = "front:edge:2",
    points: tuple[tuple[float, float], ...] = ((0.0, 0.0), (10.0, 0.0)),
) -> dict[str, object]:
    """Build a current semantic edge record with complete native provenance."""
    return {
        "piece_id": piece_id,
        "id": edge_id,
        "points": points,
        "ordinal": 2,
        "provenance": _provenance(points),
    }


def _reference(
    piece_id: str = "front",
    edge_id: str = "front:edge:2",
    points: tuple[tuple[float, float], ...] = ((0.0, 0.0), (10.0, 0.0)),
) -> EdgeReference:
    """Capture an edge using the same provenance stored in the current record."""
    return capture_edge_reference(piece_id, edge_id, points, _provenance(points))


def test_semantic_edge_id_is_deterministic() -> None:
    """Generate stable piece-scoped IDs from integer boundary indices."""
    assert semantic_edge_id("front", 2) == "front:edge:2"
    with pytest.raises(TypeError, match="ordinal must be an integer"):
        semantic_edge_id("front", cast(int, "2"))


def test_signature_is_deterministic_and_order_sensitive() -> None:
    """Hash edge coordinates and native provenance in their authored direction."""
    points = ((0.0, 0.0), (5.0, 2.0), (10.0, 0.0))
    signature = edge_signature(points, _provenance(points))
    assert signature == edge_signature(points, _provenance(points))
    reversed_points = tuple(reversed(points))
    assert signature != edge_signature(reversed_points, _provenance(reversed_points))


def test_reference_round_trips_as_document_data() -> None:
    """Serialize and restore the complete immutable semantic edge reference."""
    reference = _reference()
    assert EdgeReference.from_dict(reference.as_dict()) == reference


def test_resolver_uses_semantic_id_not_ordinal() -> None:
    """Resolve the exact semantic ID even when another edge has the same ordinal."""
    reference = _reference()
    edges = [
        _edge("front", "front:edge:7"),
        _edge("front", "front:edge:2"),
    ]
    assert resolve_edge_reference(reference, edges)["id"] == "front:edge:2"


def test_missing_semantic_id_is_explicitly_invalid() -> None:
    """Report a missing identity rather than choosing an ordinal replacement."""
    reference = _reference()
    edges = [_edge("front", "front:edge:7")]
    with pytest.raises(MissingEdgeReference):
        resolve_edge_reference(reference, edges)
    assert resolve_edge_reference_status(reference, edges) == (False, "missing")


def test_changed_geometry_never_retargets_reference() -> None:
    """Reject changed geometry when its prior semantic ID still exists."""
    reference = _reference()
    changed = [_edge("front", "front:edge:2", ((0.0, 0.0), (12.0, 0.0)))]
    with pytest.raises(ChangedEdgeReference):
        resolve_edge_reference(reference, changed)
    assert resolve_edge_reference_status(reference, changed) == (False, "changed")


def test_other_piece_with_same_edge_id_does_not_match() -> None:
    """Keep same-spelled semantic IDs isolated to their owning PatternPiece."""
    reference = _reference()
    with pytest.raises(MissingEdgeReference):
        resolve_edge_reference(reference, [_edge("back", "front:edge:2")])


def test_capture_requires_native_provenance() -> None:
    """Reject references that omit authoritative Sketcher provenance."""
    with pytest.raises(TypeError):
        capture_edge_reference("front", "front:edge:0", ((0.0, 0.0), (1.0, 0.0)))


def test_invalid_reference_inputs_fail_early() -> None:
    """Reject empty identities, endpoint-only signatures, and degenerate edges."""
    with pytest.raises(ValueError):
        EdgeReference("", "front:edge:0", "native-v1:abc")
    with pytest.raises(ValueError):
        EdgeReference("front", "", "native-v1:abc")
    with pytest.raises(ValueError, match="native Sketcher provenance"):
        EdgeReference("front", "front:edge:0", "abc")
    with pytest.raises(ValueError, match="at least two points"):
        edge_signature(((0.0, 0.0),), _provenance(((0.0, 0.0),)))
