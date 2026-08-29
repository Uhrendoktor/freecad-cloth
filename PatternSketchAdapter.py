"""Stable semantic references between Cloth seams and native Sketcher geometry.

The adapter deliberately treats Sketcher geometry indices as *resolution data*,
not as the semantic identity of a seam.  A sketch stores a persistent ordered
list of Cloth edge IDs.  Edits that preserve geometry cardinality retain those
IDs; topology/cardinality changes are reported as invalid instead of silently
retargeting seams.

This module is FreeCAD-independent so the reference contract can be tested in
headless CI.  FreeCAD-facing helpers are intentionally small and optional.
"""
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple


class SemanticEdgeError(ValueError):
    """Base error for invalid or unresolved semantic edge references."""


class EdgeReferenceInvalid(SemanticEdgeError):
    """Raised when a stored edge cannot be safely resolved after an edit."""


@dataclass(frozen=True)
class SemanticEdge:
    """A persistent Cloth identity and its current Sketcher geometry index."""

    id: str
    index: int


@dataclass(frozen=True)
class EdgeMap:
    """Resolved mapping between semantic edge IDs and current geometry indices."""

    ids: Tuple[str, ...]

    @property
    def count(self) -> int:
        return len(self.ids)

    def resolve(self, edge_id: str) -> SemanticEdge:
        try:
            index = self.ids.index(edge_id)
        except ValueError as exc:
            raise EdgeReferenceInvalid(
                f"semantic edge '{edge_id}' is not present in the current sketch"
            ) from exc
        return SemanticEdge(edge_id, index)


def make_edge_ids(piece_id: str, count: int) -> List[str]:
    """Return deterministic semantic IDs for a new pattern boundary."""
    if not str(piece_id).strip():
        raise ValueError("pattern piece id must not be empty")
    if count < 1:
        raise ValueError("a pattern boundary needs at least one edge")
    return [f"{piece_id}:edge:{i}" for i in range(count)]


def build_edge_map(ids: Sequence[str], geometry_count: int) -> EdgeMap:
    """Validate persisted IDs against current Sketcher geometry cardinality.

    Cardinality mismatch is treated as unsafe topology change.  This conservative
    rule is intentional: without a stronger geometric correspondence algorithm,
    keeping seam IDs attached by position could silently sew the wrong edges.
    """
    normalized = tuple(str(edge_id).strip() for edge_id in ids)
    if any(not edge_id for edge_id in normalized):
        raise EdgeReferenceInvalid("semantic edge IDs must not be empty")
    if len(set(normalized)) != len(normalized):
        raise EdgeReferenceInvalid("semantic edge IDs must be unique")
    if geometry_count < 0:
        raise ValueError("geometry count must not be negative")
    if len(normalized) != geometry_count:
        raise EdgeReferenceInvalid(
            "pattern topology changed: stored semantic edge count "
            f"({len(normalized)}) differs from Sketcher geometry count ({geometry_count})"
        )
    return EdgeMap(normalized)


def resolve_edge(ids: Sequence[str], geometry_count: int, edge_id: str) -> SemanticEdge:
    """Safely resolve a persisted semantic edge ID to a current geometry index."""
    return build_edge_map(ids, geometry_count).resolve(edge_id)


def validate_reference_set(
    ids: Sequence[str], geometry_count: int, references: Iterable[str]
) -> None:
    """Validate all seam references against the current sketch in one pass."""
    mapping = build_edge_map(ids, geometry_count)
    for edge_id in references:
        mapping.resolve(str(edge_id))


def get_sketch_edge_ids(sketch) -> Tuple[str, ...]:
    """Read the persisted semantic IDs from a native Sketcher object."""
    ids = getattr(sketch, "SemanticEdgeIds", None)
    if ids is None:
        raise EdgeReferenceInvalid("sketch has no Cloth semantic edge IDs")
    return tuple(str(value) for value in ids)


def resolve_sketch_edge(sketch, edge_id: str) -> SemanticEdge:
    """Resolve a semantic edge against the current native Sketcher geometry.

    ``GeometryCount`` is preferred where available; otherwise the Sketcher
    ``Geometry`` collection is used.  No FreeCAD import is required by this
    module, which keeps the contract usable from normal unit tests.
    """
    geometry = getattr(sketch, "Geometry", None)
    if geometry is None:
        raise EdgeReferenceInvalid("sketch does not expose Geometry")
    return resolve_edge(get_sketch_edge_ids(sketch), len(geometry), edge_id)
