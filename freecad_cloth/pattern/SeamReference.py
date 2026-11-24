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
import math
from collections.abc import Iterable, Mapping, Sequence
from typing import Self

from freecad_cloth.common.JsonTypes import JsonValue

Point = tuple[float, float]
type _ProvenanceValue = JsonValue | tuple["_ProvenanceValue", ...]
type _EdgeRecordValue = JsonValue | tuple["_EdgeRecordValue", ...]
type _EdgeRecord = Mapping[str, _EdgeRecordValue]

from pydantic.dataclasses import dataclass as pydantic_dataclass

NATIVE_SIGNATURE_PREFIX = "native-v1:"
NATIVE_SIGNATURE_PREFIX_V2 = "native-v2:"
V2_COORDINATE_PRECISION = 6
V2_SAMPLE_COUNT = 64


def _normalize_provenance(value: _ProvenanceValue, precision: int = 9) -> JsonValue:
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
        if not str(self.signature).startswith(
            (NATIVE_SIGNATURE_PREFIX, NATIVE_SIGNATURE_PREFIX_V2)
        ):
            msg = "signature must contain native Sketcher provenance"
            raise ValueError(msg)

    def as_dict(self):
        """Serialize this reference to a dictionary.

        Returns:
            A JSON-compatible mapping of the semantic edge identity and signature."""
        return {
            "piece_id": self.piece_id,
            "edge_id": self.edge_id,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, JsonValue]) -> Self:
        """Create a reference from a serialized dictionary.

        Args:
            value: Mapping containing the piece ID, edge ID, and native signature.

        Returns:
            Validated immutable edge reference.

        Raises:
            ValueError: If any required identity field is absent or invalid."""
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
    provenance: _ProvenanceValue,
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


def _resample_edge_points(
    samples: Sequence[Sequence[float]],
    sample_count: int = V2_SAMPLE_COUNT,
) -> tuple[tuple[float, float, float], ...]:
    """Resample one sampled native curve at equal arc-length intervals.

    Args:
        samples: Ordered XYZ samples from the current PatternIR boundary.
        sample_count: Number of points retained in the canonical fingerprint.

    Returns:
        Equal-arc-length samples in the source edge's current direction.

    Raises:
        ValueError: If samples are malformed, non-finite, or degenerate.
    """
    if len(samples) < 2 or sample_count < 2:
        msg = "native edge fingerprint needs at least two samples"
        raise ValueError(msg)
    points: list[tuple[float, float, float]] = []
    for point in samples:
        if len(point) < 2:
            msg = "native edge fingerprint samples need at least two coordinates"
            raise ValueError(msg)
        x = float(point[0])
        y = float(point[1])
        z = float(point[2]) if len(point) > 2 else 0.0
        if not all(math.isfinite(value) for value in (x, y, z)):
            msg = "native edge fingerprint samples must be finite"
            raise ValueError(msg)
        points.append((x, y, z))
    segment_lengths = tuple(
        math.dist(start, end) for start, end in zip(points, points[1:], strict=True)
    )
    total_length = sum(segment_lengths)
    if total_length <= 1e-12:
        msg = "native edge fingerprint samples must have positive length"
        raise ValueError(msg)
    cumulative = [0.0]
    for length in segment_lengths:
        cumulative.append(cumulative[-1] + length)
    result: list[tuple[float, float, float]] = []
    segment_index = 0
    for sample_index in range(sample_count):
        target = total_length * sample_index / (sample_count - 1)
        while (
            segment_index < len(segment_lengths) - 1
            and cumulative[segment_index + 1] < target
        ):
            segment_index += 1
        start, end = points[segment_index], points[segment_index + 1]
        length = segment_lengths[segment_index]
        fraction = (target - cumulative[segment_index]) / length if length > 1e-12 else 0.0
        result.append(
            tuple(
                start[axis] + (end[axis] - start[axis]) * fraction
                for axis in range(3)
            )
        )
    return tuple(result)


def edge_signature_v2(
    points: Sequence[Point],
    provenance: _ProvenanceValue,
    precision: int = V2_COORDINATE_PRECISION,
) -> str:
    """Hash semantic curve geometry independently of native parameterization.

    Version 2 fingerprints equal-arc-length XYZ samples with a canonical
    direction. It intentionally excludes the native parameter interval:
    Sketcher may serialize the same shallow curve with a shifted parameter
    origin or reversed traversal while its geometric boundary remains intact.

    Args:
        points: Ordered 2D edge endpoints in the current native record.
        provenance: PatternIR/Sketcher curve kind, parameter range and XYZ samples.
        precision: Decimal millimetres retained in the canonical sample fingerprint.

    Returns:
        Native-v2 SHA-256 signature for the semantic edge.

    Raises:
        ValueError: If the native PatternIR provenance is missing or malformed.
    """
    if len(points) < 2:
        msg = "an edge needs at least two points"
        raise ValueError(msg)
    if provenance is None:
        msg = "native Sketcher edge provenance is required"
        raise ValueError(msg)
    normalized = _normalize_provenance(provenance, precision)
    if (
        not isinstance(normalized, list)
        or len(normalized) != 5
        or normalized[0] != "PatternIR"
        or normalized[1] != "Sketcher"
        or not isinstance(normalized[2], str)
        or not isinstance(normalized[4], list)
    ):
        msg = "native-v2 fingerprints require PatternIR Sketcher curve provenance"
        raise ValueError(msg)
    samples: list[tuple[float, float, float]] = []
    for point in normalized[4]:
        if not isinstance(point, list) or len(point) < 2:
            msg = "native-v2 PatternIR samples must contain XYZ coordinates"
            raise ValueError(msg)
        raw_coordinates = (point[0], point[1], point[2] if len(point) > 2 else 0.0)
        if any(
            not isinstance(value, (int, float)) or isinstance(value, bool)
            for value in raw_coordinates
        ):
            msg = "native-v2 PatternIR samples must contain numeric XYZ coordinates"
            raise ValueError(msg)
        coordinates = (
            float(raw_coordinates[0]),
            float(raw_coordinates[1]),
            float(raw_coordinates[2]),
        )
        if not all(math.isfinite(value) for value in coordinates):
            msg = "native-v2 PatternIR samples must be finite"
            raise ValueError(msg)
        samples.append((coordinates[0], coordinates[1], coordinates[2]))
    sampled = _resample_edge_points(samples)
    forward = tuple(
        tuple(round(value, precision) for value in point) for point in sampled
    )
    canonical_samples = min(forward, tuple(reversed(forward)))
    canonical_endpoints = (
        (canonical_samples[0][0], canonical_samples[0][1]),
        (canonical_samples[-1][0], canonical_samples[-1][1]),
    )
    payload = {
        "schema": 2,
        "source": "PatternIR/Sketcher",
        "curve_kind": normalized[2],
        "points": canonical_endpoints,
        "samples_xyz_mm": canonical_samples,
        "coordinate_precision_mm": 10.0 ** -precision,
    }
    encoded = json.dumps(
        payload,
        separators=(",", ":"),
        ensure_ascii=True,
        sort_keys=True,
    )
    return NATIVE_SIGNATURE_PREFIX_V2 + hashlib.sha256(encoded.encode("ascii")).hexdigest()


def capture_edge_reference_v2(
    piece_id: str,
    edge_id: str,
    points: Sequence[Point],
    provenance: _ProvenanceValue,
) -> EdgeReference:
    """Capture a serialization-stable native-v2 semantic edge reference."""
    return EdgeReference(
        str(piece_id),
        str(edge_id),
        edge_signature_v2(points, provenance),
    )


def capture_edge_reference(
    piece_id: str,
    edge_id: str,
    points: Sequence[Point],
    provenance: _ProvenanceValue,
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
    edges: Iterable[_EdgeRecord],
) -> _EdgeRecord:
    """Resolve a reference against current edges without ordinal retargeting.

    Each edge mapping must contain ``id``, ``points``, and native ``provenance``.
    The exact semantic ID is checked against the current provenance signature.
    Missing IDs or changed geometry raise explicit errors rather than returning
    another edge with a coincidentally similar ordinal.

    Args:
        reference: Persisted semantic edge identity and native geometry signature.
        edges: Current edge records with IDs, sampled points, and provenance.

    Returns:
        Current edge record matching the exact semantic ID and geometry signature.

    Raises:
        MissingEdgeReference: If the referenced semantic edge no longer exists.
        ChangedEdgeReference: If current geometry or provenance differs from the saved signature."""
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
    current = (
        edge_signature_v2(points, provenance=provenance)
        if reference.signature.startswith(NATIVE_SIGNATURE_PREFIX_V2)
        else edge_signature(points, provenance=provenance)
    )
    if current != reference.signature:
        msg = f"semantic edge reference {reference.edge_id} geometry/provenance changed"
        raise ChangedEdgeReference(msg)
    return match


def resolve_edge_reference_status(
    reference: EdgeReference, edges: Iterable[_EdgeRecord]
) -> tuple[bool, str]:
    """Return ``(valid, reason)`` without raising for UI validation paths.

    Args:
        reference: Persisted semantic edge identity and native geometry signature.
        edges: Current edge records with IDs, sampled points, and provenance.

    Returns:
        Boolean validity and a stable reason label: valid, missing, or changed."""
    try:
        resolve_edge_reference(reference, edges)
    except MissingEdgeReference:
        return False, "missing"
    except ChangedEdgeReference:
        return False, "changed"
    return True, "valid"
