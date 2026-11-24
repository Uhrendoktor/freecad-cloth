# Copyright (C) 2026 FreeCAD Cloth contributors
"""Contract tests for provenance-backed semantic seam-edge references."""

from typing import TypedDict, cast

import pytest

from freecad_cloth.pattern.SeamReference import (
    ChangedEdgeReference,
    EdgeReference,
    MissingEdgeReference,
    capture_edge_reference,
    capture_edge_reference_v2,
    edge_signature,
    edge_signature_v2,
    resolve_edge_reference,
    resolve_edge_reference_status,
    semantic_edge_id,
)

type _Point2D = tuple[float, float]
type _EdgeProvenance = tuple[str, str, str, tuple[float, float], tuple[_Point2D, ...]]


class _EdgeRecord(TypedDict):
    """Semantic edge record persisted by the seam-reference adapter."""

    piece_id: str
    id: str
    points: tuple[_Point2D, ...]
    ordinal: int
    provenance: _EdgeProvenance


def _provenance(points: tuple[_Point2D, ...]) -> _EdgeProvenance:
    """Build the same native line provenance used by a test edge record."""
    return ("PatternIR", "Sketcher", "line", (0.0, 1.0), tuple(points))


def _edge(
    piece_id: str = "front",
    edge_id: str = "front:edge:2",
    points: tuple[_Point2D, ...] = ((0.0, 0.0), (10.0, 0.0)),
) -> _EdgeRecord:
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
    points: tuple[_Point2D, ...] = ((0.0, 0.0), (10.0, 0.0)),
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


def test_native_v2_fingerprint_ignores_parameter_origin_and_direction() -> None:
    """Equivalent Sketcher curve loci must hash identically after serialization."""
    samples = tuple(
        (10.0 + 4.0 * math.sin(math.pi * index / 63.0), 20.0 * index / 63.0, 0.0)
        for index in range(64)
    )
    forward = ("PatternIR", "Sketcher", "arc", (0.0, math.pi), samples)
    shifted_reverse = (
        "PatternIR",
        "Sketcher",
        "arc",
        (2.0 * math.pi, 3.0 * math.pi),
        tuple(reversed(samples)),
    )
    first = capture_edge_reference_v2(
        "front",
        "front:edge:1",
        ((samples[0][0], samples[0][1]), (samples[-1][0], samples[-1][1])),
        forward,
    )
    second = capture_edge_reference_v2(
        "front",
        "front:edge:1",
        ((samples[-1][0], samples[-1][1]), (samples[0][0], samples[0][1])),
        shifted_reverse,
    )

    assert first.signature.startswith("native-v2:")
    assert first.signature == second.signature
    assert edge_signature_v2(
        ((0.0, 0.0), (10.0, 0.0)),
        ("PatternIR", "Sketcher", "line", (0.0, 1.0), ((0.0, 0.0), (10.0, 0.0))),
    ).startswith("native-v2:")


def test_native_v2_fingerprint_rejects_real_geometry_edits() -> None:
    """A real curve change remains visible after geometry canonicalization."""
    samples = tuple(
        (10.0 + 4.0 * math.sin(math.pi * index / 63.0), 20.0 * index / 63.0, 0.0)
        for index in range(64)
    )
    provenance = ("PatternIR", "Sketcher", "arc", (0.0, math.pi), samples)
    reference = capture_edge_reference_v2(
        "front",
        "front:edge:1",
        ((samples[0][0], samples[0][1]), (samples[-1][0], samples[-1][1])),
        provenance,
    )
    changed_samples = list(samples)
    changed_samples[31] = (changed_samples[31][0] + 0.05, changed_samples[31][1], 0.0)
    changed_provenance = (
        "PatternIR",
        "Sketcher",
        "arc",
        (0.0, math.pi),
        tuple(changed_samples),
    )
    changed_edge = {
        "piece_id": "front",
        "id": "front:edge:1",
        "points": ((samples[0][0], samples[0][1]), (samples[-1][0], samples[-1][1])),
        "ordinal": 1,
        "provenance": changed_provenance,
    }

    with pytest.raises(ChangedEdgeReference):
        resolve_edge_reference(reference, (changed_edge,))


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
