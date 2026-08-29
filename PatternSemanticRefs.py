"""Stable semantic references between Cloth seams and Sketcher geometry.

This module is deliberately FreeCAD-independent.  It defines the persistent
identity contract used by FreeCAD adapters without making the pattern model
or solver depend on Sketcher topology numbering.
"""
from dataclasses import dataclass
import re
from typing import Iterable, Mapping, Optional, Sequence, Tuple


_EDGE_RE = re.compile(r"^(?P<piece>[^:]+):edge:(?P<index>[0-9]+)$")


@dataclass(frozen=True)
class SemanticEdgeRef:
    """Stable identity for one pattern boundary element.

    ``piece_id`` is the persistent PatternPiece identity. ``edge_id`` is a
    Cloth-owned semantic identity and is not intended to mirror FreeCAD's
    transient ``EdgeN`` topology number.
    """

    piece_id: str
    edge_id: str

    def __post_init__(self):
        if not str(self.piece_id).strip():
            raise ValueError("piece_id must not be empty")
        if not str(self.edge_id).strip():
            raise ValueError("edge_id must not be empty")

    @property
    def key(self) -> str:
        return f"{self.piece_id}:{self.edge_id}"

    @classmethod
    def from_index(cls, piece_id: str, index: int) -> "SemanticEdgeRef":
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            raise ValueError("edge index must be a non-negative integer")
        return cls(str(piece_id), f"edge:{index}")

    @classmethod
    def parse(cls, value: str) -> "SemanticEdgeRef":
        match = _EDGE_RE.match(str(value))
        if not match:
            raise ValueError("invalid semantic edge reference")
        return cls(match.group("piece"), f"edge:{int(match.group('index'))}")


@dataclass(frozen=True)
class EdgeResolution:
    """Result of resolving a semantic edge against current Sketch geometry."""

    reference: SemanticEdgeRef
    geometry_index: Optional[int]
    valid: bool
    reason: str = ""


def semantic_edge_ids(piece_id: str, count: int) -> Tuple[str, ...]:
    """Return deterministic initial semantic IDs for a piece boundary."""
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError("count must be a non-negative integer")
    return tuple(SemanticEdgeRef.from_index(piece_id, i).key for i in range(count))


def resolve_edge(ref: SemanticEdgeRef, semantic_ids: Sequence[str]) -> EdgeResolution:
    """Resolve a stable semantic ID to its current geometry index.

    Resolution is exact: an unknown ID is invalid rather than falling back to
    an EdgeN index. This prevents a topology edit from silently sewing the
    wrong boundary.
    """
    try:
        index = tuple(semantic_ids).index(ref.key)
    except ValueError:
        return EdgeResolution(ref, None, False, "semantic edge no longer exists")
    return EdgeResolution(ref, index, True)


def validate_unique_edge_ids(ids: Iterable[str]) -> None:
    """Reject duplicate or malformed semantic IDs before persistence."""
    seen = set()
    for value in ids:
        ref = SemanticEdgeRef.parse(value)
        if ref.key in seen:
            raise ValueError(f"duplicate semantic edge ID: {ref.key}")
        seen.add(ref.key)


def migrate_index_reference(piece_id: str, index: int, semantic_ids: Sequence[str]) -> SemanticEdgeRef:
    """Convert a legacy outline index to a semantic ID when possible."""
    ref = SemanticEdgeRef.from_index(piece_id, index)
    if ref.key not in semantic_ids:
        raise ValueError("legacy edge index cannot be resolved to semantic geometry")
    return ref
