# Copyright (C) 2026 FreeCAD Cloth contributors
"""Stable semantic edge references for Cloth sewing objects.

The FreeCAD workbench may expose native sub-elements such as ``Edge1`` while
editing, but persistent sewing relationships must not silently follow changed
edge numbering.  This adapter records a semantic edge id plus a deterministic
geometry signature and resolves only an exact id/signature match.

The module is FreeCAD-independent so it can be used by document adapters and
headless tests without importing the GUI runtime.
"""

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence

Point = tuple[float, float]

from pydantic.dataclasses import dataclass as pydantic_dataclass

NATIVE_SIGNATURE_PREFIX = "native-v1:"


def _normalize_provenance(value, precision=9):
    """Convert native PatternIR provenance into deterministic JSON data."""
    if isinstance(value, Mapping):
        return {
            str(key): _normalize_provenance(value[key], precision) for key in sorted(value, key=str)
        }
    if isinstance(value, (list, tuple)):
        return [_normalize_provenance(item, precision) for item in value]
    if isinstance(value, float):
        return round(value, precision)
    if isinstance(value, int):
        return value
    return str(value)


class EdgeReferenceError(ValueError):
    """Base error for invalid or unresolvable semantic edge references."""


class MissingEdgeReference(EdgeReferenceError):
    """The semantic edge id no longer exists on its pattern piece."""


class ChangedEdgeReference(EdgeReferenceError):
    """The semantic id exists but its geometry no longer matches."""


@pydantic_dataclass(frozen=True)
class EdgeReference:
    """Persistent identity and fingerprint for one pattern boundary edge."""

    piece_id: str
    edge_id: str
    signature: str

    def __post_init__(self):
        if not str(self.piece_id).strip():
            msg = "piece_id must not be empty"
            raise ValueError(msg)
        if not str(self.edge_id).strip():
            msg = "edge_id must not be empty"
            raise ValueError(msg)
        if not str(self.signature).startswith(NATIVE_SIGNATURE_PREFIX):
            msg = "signature must contain native Sketcher provenance"
            raise ValueError(msg)

    def as_dict(self):
        """Serialize this reference to a dictionary."""
        return {
            "piece_id": self.piece_id,
            "edge_id": self.edge_id,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]):
        """Create a reference from a serialized dictionary."""
        try:
            return cls(
                str(value["piece_id"]),
                str(value["edge_id"]),
                str(value["signature"]),
            )
        except KeyError as exc:
            msg = f"edge reference is missing {exc.args[0]}"
            raise ValueError(msg) from exc


def semantic_edge_id(piece_id: str, ordinal: int) -> str:
    """Return a stable ID for an indexed generated boundary edge.

    Args:
        piece_id: Persistent identity of the PatternPiece that owns the edge.
        ordinal: Non-negative integer index assigned during boundary generation.

    Returns:
        Stable piece-scoped ID for the generated boundary edge.

    Raises:
        ValueError: If the piece identity or ordinal is invalid.
        TypeError: If ordinal is not an integer.
    """
    if not str(piece_id).strip():
        msg = "piece_id must not be empty"
        raise ValueError(msg)
    if isinstance(ordinal, bool) or not isinstance(ordinal, int):
        msg = "edge ordinal must be an integer"
        raise TypeError(msg)
    if ordinal < 0:
        msg = "edge ordinal must be non-negative"
        raise ValueError(msg)
    return "%s:edge:%d" % (piece_id, ordinal)


def edge_signature(
    points: Sequence[Point],
    provenance: object,
    precision: int = 9,
) -> str:
    """Hash ordered edge coordinates together with required native provenance.

    Args:
        points: Ordered 2D samples representing the edge.
        provenance: PatternIR curve kind, parameter range, and native samples.
        precision: Decimal precision for stable coordinate serialization.

    Returns:
        Native-versioned SHA-256 signature for the current edge.

    Raises:
        ValueError: If the edge has fewer than two points or no native provenance.
    """
    if len(points) < 2:
        msg = "an edge needs at least two points"
        raise ValueError(msg)
    if provenance is None:
        msg = "native Sketcher edge provenance is required"
        raise ValueError(msg)
    normalized = [
        (round(float(point[0]), precision), round(float(point[1]), precision)) for point in points
    ]
    payload = {
        "points": normalized,
        "provenance": _normalize_provenance(provenance, precision),
    }
    encoded = json.dumps(
        payload,
        separators=(",", ":"),
        ensure_ascii=True,
        sort_keys=True,
    )
    return NATIVE_SIGNATURE_PREFIX + hashlib.sha256(encoded.encode("ascii")).hexdigest()


def capture_edge_reference(
    piece_id: str,
    edge_id: str,
    points: Sequence[Point],
    provenance: object,
) -> EdgeReference:
    """Capture semantic identity plus required native Sketcher provenance.

    Args:
        piece_id: Persistent identity of the PatternPiece.
        edge_id: Persistent identity assigned to a Sketch.Geometry edge.
        points: Ordered 2D samples representing the current edge.
        provenance: PatternIR curve kind, parameter range, and native samples.

    Returns:
        Immutable reference with a native-versioned geometry signature.
    """
    return EdgeReference(
        str(piece_id),
        str(edge_id),
        edge_signature(points, provenance=provenance),
    )


def resolve_edge_reference(
    reference: EdgeReference,
    edges: Iterable[Mapping[str, object]],
) -> Mapping[str, object]:
    """Resolve a reference against current edges without ordinal retargeting.

    Each edge mapping must contain ``id`, ``points`, and native ``provenance``.
    The exact semantic ID is checked against the current provenance signature.
    Missing IDs or changed geometry raise explicit errors rather than returning
    another edge with a coincidentally similar ordinal.
    """
    candidates = [
        edge
        for edge in edges
        if str(edge.get("piece_id", reference.piece_id)) == reference.piece_id
    ]
    match = next(
        (edge for edge in candidates if str(edge.get("id", "")) == reference.edge_id), None
    )
    if match is None:
        msg = f"semantic edge reference {reference.edge_id} is missing from pattern piece {reference.piece_id}"
        raise MissingEdgeReference(msg)
    points = match.get("points")
    if points is None:
        msg = f"semantic edge reference {reference.edge_id} has no current geometry"
        raise ChangedEdgeReference(msg)
    provenance = match.get("provenance")
    if provenance is None or not str(reference.signature).startswith(NATIVE_SIGNATURE_PREFIX):
        msg = f"semantic edge reference {reference.edge_id} lacks native Sketcher provenance"
        raise ChangedEdgeReference(msg)
    current = edge_signature(points, provenance=provenance)
    if current != reference.signature:
        msg = f"semantic edge reference {reference.edge_id} geometry/provenance changed"
        raise ChangedEdgeReference(msg)
    return match


def resolve_edge_reference_status(
    reference: EdgeReference, edges: Iterable[Mapping[str, object]]
) -> tuple[bool, str]:
    """Return ``(valid, reason)`` without raising for UI validation paths."""
    try:
        resolve_edge_reference(reference, edges)
    except MissingEdgeReference:
        return False, "missing"
    except ChangedEdgeReference:
        return False, "changed"
    return True, "valid"
