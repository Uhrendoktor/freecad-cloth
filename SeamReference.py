"""Stable semantic edge references for Cloth sewing objects.

The FreeCAD workbench may expose native sub-elements such as ``Edge1`` while
editing, but persistent sewing relationships must not silently follow changed
edge numbering.  This adapter records a semantic edge id plus a deterministic
geometry signature and resolves only an exact id/signature match.

The module is FreeCAD-independent so it can be used by document adapters and
headless tests without importing the GUI runtime.
"""
from dataclasses import dataclass
import hashlib
import json
from typing import Iterable, Mapping, Optional, Sequence, Tuple

Point = Tuple[float, float]


class EdgeReferenceError(ValueError):
    """Base error for invalid or unresolvable semantic edge references."""


class MissingEdgeReference(EdgeReferenceError):
    """The semantic edge id no longer exists on its pattern piece."""


class ChangedEdgeReference(EdgeReferenceError):
    """The semantic id exists but its geometry no longer matches."""


@dataclass(frozen=True)
class EdgeReference:
    """Persistent identity and fingerprint for one pattern boundary edge."""

    piece_id: str
    edge_id: str
    signature: str

    def __post_init__(self):
        if not str(self.piece_id).strip():
            raise ValueError("piece_id must not be empty")
        if not str(self.edge_id).strip():
            raise ValueError("edge_id must not be empty")
        if not str(self.signature).strip():
            raise ValueError("signature must not be empty")

    def as_dict(self):
        return {
            "piece_id": self.piece_id,
            "edge_id": self.edge_id,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]):
        try:
            return cls(
                str(value["piece_id"]),
                str(value["edge_id"]),
                str(value["signature"]),
            )
        except KeyError as exc:
            raise ValueError("edge reference is missing %s" % exc.args[0]) from exc


def semantic_edge_id(piece_id: str, ordinal: int) -> str:
    """Return the canonical fallback id used for generated polygon edges."""
    if not str(piece_id).strip():
        raise ValueError("piece_id must not be empty")
    ordinal = int(ordinal)
    if ordinal < 0:
        raise ValueError("edge ordinal must be non-negative")
    return "%s:edge:%d" % (piece_id, ordinal)


def edge_signature(points: Sequence[Point], precision: int = 9) -> str:
    """Hash an ordered edge polyline after deterministic float normalization."""
    if len(points) < 2:
        raise ValueError("an edge needs at least two points")
    normalized = [
        (round(float(point[0]), precision), round(float(point[1]), precision))
        for point in points
    ]
    payload = json.dumps(normalized, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def capture_edge_reference(
    piece_id: str,
    edge_id: str,
    points: Sequence[Point],
) -> EdgeReference:
    """Capture the current semantic identity and geometry fingerprint."""
    return EdgeReference(str(piece_id), str(edge_id), edge_signature(points))


def resolve_edge_reference(
    reference: EdgeReference,
    edges: Iterable[Mapping[str, object]],
) -> Mapping[str, object]:
    """Resolve a reference against current edges without ordinal retargeting.

    Each edge mapping must contain ``id`` and ``points``.  The first exact id
    match is checked against the captured geometry signature.  A missing id or
    changed geometry raises an explicit error rather than returning another
    edge with a coincidentally similar ordinal.
    """
    candidates = [edge for edge in edges if str(edge.get("piece_id", reference.piece_id)) == reference.piece_id]
    match = next((edge for edge in candidates if str(edge.get("id", "")) == reference.edge_id), None)
    if match is None:
        raise MissingEdgeReference(
            "semantic edge reference %s is missing from pattern piece %s"
            % (reference.edge_id, reference.piece_id)
        )
    points = match.get("points")
    if points is None:
        raise ChangedEdgeReference(
            "semantic edge reference %s has no current geometry" % reference.edge_id
        )
    current = edge_signature(points)
    if current != reference.signature:
        raise ChangedEdgeReference(
            "semantic edge reference %s geometry changed" % reference.edge_id
        )
    return match


def resolve_edge_reference_status(reference: EdgeReference, edges: Iterable[Mapping[str, object]]):
    """Return ``(valid, reason)`` without raising for UI validation paths."""
    try:
        resolve_edge_reference(reference, edges)
    except MissingEdgeReference:
        return False, "missing"
    except ChangedEdgeReference:
        return False, "changed"
    return True, "valid"
