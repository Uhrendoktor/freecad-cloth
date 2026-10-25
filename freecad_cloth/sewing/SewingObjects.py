# Copyright (C) 2026 FreeCAD Cloth contributors
"""FreeCAD document objects for sewing operations."""

from __future__ import annotations

import numpy as np
from math import atan2, degrees, hypot
from typing import TYPE_CHECKING, Protocol, cast

from freecad_cloth.pattern.SeamReference import ChangedEdgeReference, MissingEdgeReference
from freecad_cloth.sewing.SewingCorrespondence import (
    analyze_correspondence,
    correspondence_status_label,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from types import ModuleType


class _NativePoint(Protocol):
    """Coordinate interface exposed by FreeCAD vectors and edge vertices."""

    x: float
    y: float
    z: float


class _NativeVertex(Protocol):
    Point: _NativePoint


class _NativeEdge(Protocol):
    """Minimal geometry interface required from FreeCAD shape edges."""

    Vertexes: Sequence[_NativeVertex]

    def discretize(self, _number: int) -> Sequence[_NativePoint]: ...


class _NativePlacement(Protocol):
    def multVec(self, _vector: _NativePoint) -> _NativePoint: ...


class _SewingFeature(Protocol):
    """Properties and methods used on a dynamic FreeCAD sewing feature."""

    Label: str
    Proxy: object
    Shape: object
    SewingType: str
    Seam: object | None
    SeamId: str
    PieceA: object | None
    PieceB: object | None
    StitchGroup: str
    Alignment: str
    ReversedB: bool
    AssemblyPlacementB: object
    Tolerance: float
    RelativeTolerance: float
    CorrespondenceStatus: str
    CorrespondenceMessage: str
    CorrespondenceRecovery: str
    CorrespondenceSeverity: str
    Stitches: int
    LengthA: float
    LengthB: float
    LengthDifference: float
    StitchCount: int
    StitchPoints: list[str]
    Status: str

    def addProperty(self, _property_type: str, name: str, group: str) -> _SewingFeature: ...
    def setEditorMode(self, name: str, _mode: int) -> None: ...


class _FreeCADDocument(Protocol):
    def addObject(self, _type_id: str, name: str) -> _SewingFeature: ...


def _edge_endpoint_pair(
    native_edge: _NativeEdge,
) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """Return the 2D endpoints of a native shape edge, when available."""
    vertices = tuple(getattr(native_edge, "Vertexes", ()) or ())
    if len(vertices) < 2:
        return None
    first = getattr(vertices[0], "Point", None)
    last = getattr(vertices[-1], "Point", None)
    if first is None or last is None:
        return None
    return (
        (float(first.x), float(first.y)),
        (float(last.x), float(last.y)),
    )


def _native_edge(
    piece: object,
    edge: int,
    *,
    native_edge_record_fn: Callable[..., dict[str, object] | None] | None = None,
) -> _NativeEdge:
    """Resolve an edge through the linked native Sketcher geometry.

    Args:
        piece: PatternPiece document object whose geometry authority is Sketcher.
        edge: Index into the linked sketch's Geometry sequence.
        native_edge_record_fn: Optional provenance reader used by focused tests.

    Returns:
        The native shape edge corresponding to the requested sketch geometry.

    Raises:
        MissingEdgeReference: If Sketcher authority or an unambiguous native edge is absent.
    """
    if str(getattr(piece, "GeometryAuthority", "")).strip() != "Sketcher":
        msg = f"pattern piece {getattr(piece, 'PieceId', '')} has no native Sketcher authority"
        raise MissingEdgeReference(msg)
    sketch = getattr(piece, "Sketch", None)
    if sketch is None:
        msg = f"pattern piece {getattr(piece, 'PieceId', '')} has no linked Sketcher object"
        raise MissingEdgeReference(msg)

    index = int(edge)
    geometry = tuple(getattr(sketch, "Geometry", ()) or ())
    if index < 0 or index >= len(geometry):
        msg = f"native Sketcher edge index {index} is outside pattern piece {piece.PieceId}"
        raise MissingEdgeReference(msg)
    to_shape = getattr(geometry[index], "toShape", None)
    if callable(to_shape):
        try:
            native = to_shape()
            if native is not None:
                return cast("_NativeEdge", native)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            pass

    shape = getattr(sketch, "Shape", None)
    candidates = tuple(getattr(shape, "Edges", ()) or ())
    if not candidates:
        msg = f"native Sketcher edge {index} has no resolvable shape"
        raise MissingEdgeReference(msg)
    read_record = native_edge_record_fn
    if read_record is None:
        from freecad_cloth.pattern.PatternObjects import _native_edge_record_for_sketch_index

        read_record = _native_edge_record_for_sketch_index
    try:
        record = read_record(piece, index)
    except (AttributeError, IndexError, KeyError, RuntimeError, TypeError, ValueError) as exc:
        msg = f"native Sketcher edge {index} has no semantic provenance record"
        raise MissingEdgeReference(msg) from exc
    expected = record.get("points") if record is not None else None
    if expected is None or len(expected) != 2:
        msg = f"native Sketcher edge {index} has no authoritative endpoint pair"
        raise MissingEdgeReference(msg)

    def matches(candidate: _NativeEdge) -> bool:
        endpoints = _edge_endpoint_pair(candidate)
        if endpoints is None:
            return False
        direct = max(
            abs(endpoints[0][0] - float(expected[0][0])),
            abs(endpoints[0][1] - float(expected[0][1])),
            abs(endpoints[1][0] - float(expected[1][0])),
            abs(endpoints[1][1] - float(expected[1][1])),
        )
        reverse = max(
            abs(endpoints[0][0] - float(expected[1][0])),
            abs(endpoints[0][1] - float(expected[1][1])),
            abs(endpoints[1][0] - float(expected[0][0])),
            abs(endpoints[1][1] - float(expected[0][1])),
        )
        return min(direct, reverse) <= 1e-7

    matching_edges = tuple(candidate for candidate in candidates if matches(candidate))
    if len(matching_edges) != 1:
        msg = (
            f"native Sketcher edge {index} must match exactly one shape edge; "
            f"found {len(matching_edges)}"
        )
        raise MissingEdgeReference(msg)
    return cast("_NativeEdge", matching_edges[0])


def _edge_polyline(
    piece: object,
    edge: int,
    sample_count: int = 64,
    *,
    native_edge_record_fn: Callable[..., dict[str, object] | None] | None = None,
) -> list[tuple[float, float]]:
    """Sample a native Sketcher edge for arc-length operations.

    Args:
        piece: Sketcher-authoritative PatternPiece document object.
        edge: Index into the linked sketch's Geometry sequence.
        sample_count: Number of discretization points requested from FreeCAD.
        native_edge_record_fn: Optional native provenance reader for shape mapping.

    Returns:
        The native edge's local 2D samples in endpoint order.

    Raises:
        MissingEdgeReference: If the edge lacks native geometry or cannot be sampled.
    """
    native = _native_edge(piece, int(edge), native_edge_record_fn=native_edge_record_fn)
    try:
        values = native.discretize(max(2, int(sample_count)))
        points = [(float(point.x), float(point.y)) for point in values]
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        msg = f"native Sketcher edge {edge} could not be discretized"
        raise MissingEdgeReference(msg) from exc
    if len(points) < 2:
        msg = f"native Sketcher edge {edge} needs at least two discretization points"
        raise MissingEdgeReference(msg)
    return points


def _polyline_length(points: Sequence[tuple[float, float]]) -> float:
    """Compute polyline length using vectorized Euclidean segment norms.

    Args:
        points: Ordered local 2D coordinates along a native edge.

    Returns:
        Sum of Euclidean segment lengths in model units.
    """
    coordinates = np.asarray(points, dtype=np.float64)
    if coordinates.shape[0] < 2:
        return 0.0
    return float(np.linalg.norm(np.diff(coordinates, axis=0), axis=1).sum())


def _sample_polyline_fractions(
    points: Sequence[tuple[float, float]],
    fractions: Sequence[float],
) -> np.ndarray:
    """Vectorize normalized arc-length sampling along an ordered polyline.

    Args:
        points: Ordered local 2D coordinates along a native edge.
        fractions: Normalized arc-length positions to sample.

    Returns:
        Array of sampled coordinates with shape (len(fractions), 2).
    """
    coordinates = np.asarray(points, dtype=np.float64)
    requested = np.asarray(fractions, dtype=np.float64)
    if coordinates.ndim != 2 or coordinates.shape[1] != 2 or coordinates.shape[0] == 0:
        msg = "polyline coordinates must be a non-empty sequence of 2D points"
        raise ValueError(msg)
    if coordinates.shape[0] == 1:
        return np.repeat(coordinates, requested.size, axis=0)
    segment_lengths = np.linalg.norm(np.diff(coordinates, axis=0), axis=1)
    cumulative = np.concatenate((np.array((0.0,), dtype=np.float64), np.cumsum(segment_lengths)))
    total = float(cumulative[-1])
    if total <= 1e-12:
        return np.repeat(coordinates[:1], requested.size, axis=0)
    targets = np.clip(requested, 0.0, 1.0) * total
    indexes = np.searchsorted(cumulative[1:], targets, side="left")
    indexes = np.clip(indexes, 0, segment_lengths.size - 1)
    spans = segment_lengths[indexes]
    offsets = targets - cumulative[indexes]
    ratios = np.divide(offsets, spans, out=np.zeros_like(offsets), where=spans > 1e-12)
    return (
        coordinates[indexes]
        + (coordinates[indexes + 1] - coordinates[indexes]) * ratios[:, None]
    )


def _sample_polyline(points: Sequence[tuple[float, float]], fraction: float) -> tuple[float, float]:
    """Sample one point at normalized arc length.

    Args:
        points: Ordered 2D coordinates along a native edge.
        fraction: Requested arc-length position, clipped to the unit interval.

    Returns:
        The sampled local 2D coordinate.
    """
    sample = _sample_polyline_fractions(points, (float(fraction),))[0]
    return float(sample[0]), float(sample[1])


def _edge_length(piece: object, edge: int) -> float:
    """Measure a native Sketcher edge by its discretized arc length.

    Args:
        piece: Sketcher-authoritative PatternPiece document object.
        edge: Index into the linked Sketch.Geometry sequence.

    Returns:
        Arc length in model units.

    Raises:
        MissingEdgeReference: If the native edge cannot be resolved or sampled.
    """
    points = _edge_polyline(piece, edge)
    return _polyline_length(points)


def _seam_edge_index(
    piece: object,
    seam: object,
    prefix: str,
    *,
    resolve_document_edge_fn: Callable[..., dict[str, object] | None] | None = None,
) -> int:
    """Resolve a persistent seam ID to its native Sketch.Geometry index.

    Args:
        piece: Sketcher-authoritative PatternPiece document object.
        seam: Persisted seam carrying a semantic edge ID and signature.
        prefix: Seam side, either A or B.
        resolve_document_edge_fn: Optional signature-aware resolver for focused tests.

    Returns:
        The unique native Sketch.Geometry index for the semantic edge.

    Raises:
        MissingEdgeReference: If native authority, ID, signature, or mapping is absent.
        ChangedEdgeReference: If the stored edge signature no longer matches the sketch.
    """
    if prefix not in {"A", "B"}:
        msg = f"unsupported seam side: {prefix}"
        raise ValueError(msg)
    if str(getattr(piece, "GeometryAuthority", "")).strip() != "Sketcher":
        msg = f"seam piece {getattr(piece, 'PieceId', '')} has no native Sketcher authority"
        raise MissingEdgeReference(msg)
    sketch = getattr(piece, "Sketch", None)
    if sketch is None:
        msg = f"seam piece {getattr(piece, 'PieceId', '')} has no linked Sketcher object"
        raise MissingEdgeReference(msg)

    id_attribute = "EdgeAId" if prefix == "A" else "EdgeBId"
    signature_attribute = "EdgeASignature" if prefix == "A" else "EdgeBSignature"
    edge_id = str(getattr(seam, id_attribute, "")).strip()
    signature = str(getattr(seam, signature_attribute, "")).strip()
    if not edge_id or not signature:
        msg = f"seam {getattr(seam, 'SeamId', '')} is missing its {prefix} semantic edge reference"
        raise MissingEdgeReference(msg)

    if resolve_document_edge_fn is None:
        from freecad_cloth.pattern.PatternObjects import _resolve_document_edge

        resolve_document_edge_fn = _resolve_document_edge
    record = resolve_document_edge_fn(piece, edge_id, signature)
    if record is None or str(record.get("id", "")) != edge_id:
        msg = f"semantic edge reference {edge_id} is missing from pattern piece {piece.PieceId}"
        raise MissingEdgeReference(msg)

    semantic_ids = tuple(
        str(value).strip() for value in (getattr(sketch, "SemanticEdgeIds", ()) or ())
    )
    native_indices = [index for index, identity in enumerate(semantic_ids) if identity == edge_id]
    if len(native_indices) != 1:
        msg = (
            f"semantic seam edge {edge_id} must resolve to exactly one native Sketcher edge; "
            f"found {len(native_indices)}"
        )
        raise MissingEdgeReference(msg)
    return native_indices[0]


def _seam_length(
    piece: object,
    seam: object,
    prefix: str,
    *,
    resolve_document_edge_fn: Callable[..., dict[str, object] | None] | None = None,
) -> float:
    """Measure the selected normalized interval of a semantically referenced edge.

    Args:
        piece: Sketcher-authoritative PatternPiece document object.
        seam: Persisted seam containing the normalized interval and edge identity.
        prefix: Seam side, either A or B.
        resolve_document_edge_fn: Optional signature-aware resolver used by focused tests.

    Returns:
        Arc length of the selected native edge interval.

    Raises:
        ValueError: If the normalized interval has no positive extent.
        MissingEdgeReference: If the semantic reference cannot be resolved.
        ChangedEdgeReference: If the saved geometry signature is stale.
    """
    start = float(getattr(seam, "StartA" if prefix == "A" else "StartB"))
    end = float(getattr(seam, "EndA" if prefix == "A" else "EndB"))
    if not 0 <= start <= 1 or not 0 <= end <= 1 or start >= end:
        msg = "seam parameters must be normalized with positive extent"
        raise ValueError(msg)
    edge = _seam_edge_index(piece, seam, prefix, resolve_document_edge_fn=resolve_document_edge_fn)
    return _edge_length(piece, edge) * (end - start)


def _edge_points(
    piece: object,
    edge: int,
    start: float = 0.0,
    end: float = 1.0,
    z: float = 0.2,
    *,
    vector_factory: Callable[..., _NativePoint] | None = None,
) -> tuple[_NativePoint, _NativePoint]:
    """Return selected native edge endpoints after applying the piece Placement.

    Args:
        piece: Sketcher-authoritative PatternPiece document object.
        edge: Native Sketch.Geometry index.
        start: Normalized start position along the edge.
        end: Normalized end position along the edge.
        z: Local offset above the sketch plane.
        vector_factory: Optional FreeCAD-vector constructor for focused tests.

    Returns:
        Two native points in world coordinates when a Placement exists, otherwise local coordinates.

    Raises:
        MissingEdgeReference: If the referenced native edge cannot be resolved or sampled.
    """
    if vector_factory is None:
        import FreeCAD as App

        vector_factory = App.Vector

    points = _edge_polyline(piece, edge)
    samples = _sample_polyline_fractions(points, (start, end))
    p0 = tuple(float(value) for value in samples[0])
    p1 = tuple(float(value) for value in samples[1])
    local0 = vector_factory(p0[0], p0[1], z)
    local1 = vector_factory(p1[0], p1[1], z)
    placement = getattr(piece, "Placement", None)
    if placement is not None:
        native_placement = cast("_NativePlacement", placement)
        return native_placement.multVec(cast("_NativePoint", local0)), native_placement.multVec(
            cast("_NativePoint", local1)
        )
    return cast("_NativePoint", local0), cast("_NativePoint", local1)


def _resolved_edge(
    piece: object,
    seam: object,
    prefix: str,
    *,
    resolve_document_edge_fn: Callable[..., dict[str, object] | None] | None = None,
) -> int:
    """Resolve the semantic seam identity to a native edge index.

    Args:
        piece: Sketcher-authoritative PatternPiece document object.
        seam: Persisted seam referencing the requested edge.
        prefix: Seam side, either A or B.
        resolve_document_edge_fn: Optional signature-aware resolver for focused tests.

    Returns:
        Native Sketch.Geometry index for the requested semantic edge.
    """
    return _seam_edge_index(piece, seam, prefix, resolve_document_edge_fn=resolve_document_edge_fn)


def _edge_samples(
    piece: object,
    edge: int,
    start: float,
    end: float,
    count: int,
    z: float = 0.2,
    transform_to_world: bool = True,
    *,
    vector_factory: Callable[..., _NativePoint] | None = None,
) -> list[_NativePoint]:
    """Return evenly arc-length-spaced points over a normalized edge range.

    Args:
        piece: Sketcher-authoritative PatternPiece document object.
        edge: Native Sketch.Geometry index.
        start: Normalized starting position along the edge.
        end: Normalized ending position along the edge.
        count: Number of samples, at least two.
        z: Local offset above the sketch plane.
        transform_to_world: Whether to apply the piece Placement.
        vector_factory: Optional FreeCAD-vector constructor used by focused tests.

    Returns:
        Evenly arc-length-spaced FreeCAD vectors.

    Raises:
        ValueError: If fewer than two samples are requested.
        MissingEdgeReference: If native geometry cannot be sampled.
    """
    if count < 2:
        msg = "correspondence requires at least two samples"
        raise ValueError(msg)
    if vector_factory is None:
        import FreeCAD as App

        vector_factory = App.Vector

    points = _edge_polyline(piece, edge)
    fractions = np.linspace(float(start), float(end), count, dtype=np.float64)
    samples = _sample_polyline_fractions(points, fractions)
    placement = getattr(piece, "Placement", None)
    result = []
    for x_value, y_value in samples:
        vector = cast("_NativePoint", vector_factory(float(x_value), float(y_value), float(z)))
        result.append(
            cast("_NativePlacement", placement).multVec(vector)
            if placement is not None and transform_to_world
            else vector
        )
    return result


def _alignment_placement(
    piece_a: object,
    piece_b: object,
    seam: object,
    *,
    app_module: ModuleType | None = None,
    vector_factory: Callable[..., _NativePoint] | None = None,
    resolve_document_edge_fn: Callable[..., dict[str, object] | None] | None = None,
) -> object:
    """Calculate the placement that aligns side B with side A's native endpoints.

    Args:
        piece_a: Pattern piece defining the fixed seam side.
        piece_b: Pattern piece to reposition.
        seam: Persisted seam referencing native edges on both pieces.
        app_module: Optional FreeCAD module for focused tests.
        vector_factory: Optional native-vector constructor.
        resolve_document_edge_fn: Optional signature-aware resolver for focused tests.

    Returns:
        Native FreeCAD placement aligning the selected seam endpoints.

    Raises:
        MissingEdgeReference: If either semantic seam reference is absent or stale.
        ChangedEdgeReference: If either referenced edge changed after seam creation.
    """
    if app_module is None:
        import FreeCAD as app_module
    if vector_factory is None:
        vector_factory = app_module.Vector

    a0, a1 = _edge_points(
        piece_a,
        _resolved_edge(piece_a, seam, "A", resolve_document_edge_fn=resolve_document_edge_fn),
        float(seam.StartA),
        float(seam.EndA),
        vector_factory=vector_factory,
    )
    b0, b1 = _edge_points(
        piece_b,
        _resolved_edge(piece_b, seam, "B", resolve_document_edge_fn=resolve_document_edge_fn),
        float(seam.StartB),
        float(seam.EndB),
        vector_factory=vector_factory,
    )
    if bool(getattr(seam, "ReversedB", False)):
        b0, b1 = b1, b0
    avx, avy = a1.x - a0.x, a1.y - a0.y
    bvx, bvy = b1.x - b0.x, b1.y - b0.y
    if hypot(avx, avy) < 1e-12 or hypot(bvx, bvy) < 1e-12:
        return app_module.Placement()
    angle = degrees(atan2(avy, avx) - atan2(bvy, bvx))
    import math

    radians = math.radians(angle)
    rx = b0.x * math.cos(radians) - b0.y * math.sin(radians)
    ry = b0.x * math.sin(radians) + b0.y * math.cos(radians)
    translation = vector_factory(a0.x - rx, a0.y - ry, a0.z - b0.z)
    return app_module.Placement(translation, app_module.Rotation(vector_factory(0, 0, 1), angle))


def _seam_correspondence(
    piece_a: object,
    piece_b: object,
    seam: object,
    count: int,
    alignment: str = "endpoints",
    *,
    vector_factory: Callable[..., _NativePoint] | None = None,
    resolve_document_edge_fn: Callable[..., dict[str, object] | None] | None = None,
) -> list[tuple[_NativePoint, _NativePoint]]:
    """Build A/B stitch points from native edges and normalized seam ranges.

    Args:
        piece_a: Pattern piece supplying seam side A.
        piece_b: Pattern piece supplying seam side B.
        seam: Persisted semantic seam between the pieces.
        count: Number of correspondence samples, at least two.
        alignment: Supported sampling mode, endpoints or uniform.
        vector_factory: Optional native-vector constructor for focused tests.
        resolve_document_edge_fn: Optional signature-aware resolver for focused tests.

    Returns:
        Ordered point pairs corresponding to the selected seam intervals.

    Raises:
        ValueError: If count or alignment is invalid.
        MissingEdgeReference: If either semantic seam reference is absent.
        ChangedEdgeReference: If either saved edge signature is stale.
    """
    if count < 2:
        msg = "correspondence requires at least two samples"
        raise ValueError(msg)
    alignment = str(alignment or "endpoints")
    if alignment not in ("endpoints", "uniform"):
        msg = f"unsupported sewing alignment: {alignment}"
        raise ValueError(msg)
    edge_a = _resolved_edge(piece_a, seam, "A", resolve_document_edge_fn=resolve_document_edge_fn)
    edge_b = _resolved_edge(piece_b, seam, "B", resolve_document_edge_fn=resolve_document_edge_fn)
    a_points = _edge_samples(
        piece_a, edge_a, float(seam.StartA), float(seam.EndA), count, vector_factory=vector_factory
    )
    b_points = _edge_samples(
        piece_b, edge_b, float(seam.StartB), float(seam.EndB), count, vector_factory=vector_factory
    )
    if bool(getattr(seam, "ReversedB", False)):
        b_points.reverse()
    return list(zip(a_points, b_points, strict=False))


class SewingOperationProxy:
    """Public data model or service class for SewingOperationProxy."""

    Type = "ClothSewingOperation"

    def execute(
        self,
        obj: _SewingFeature,
        *,
        app_module: ModuleType | None = None,
        part_module: ModuleType | None = None,
        vector_factory: Callable[..., _NativePoint] | None = None,
        resolve_document_edge_fn: Callable[..., dict[str, object] | None] | None = None,
    ) -> None:
        """Recompute sewing metrics and shape from the current semantic seam.

        Args:
            obj: FreeCAD sewing-operation feature being recomputed.
            app_module: Optional FreeCAD module supplied by focused tests.
            part_module: Optional Part module supplied by focused tests.
            vector_factory: Optional FreeCAD-vector constructor.
            resolve_document_edge_fn: Optional signature-aware resolver for focused tests.

        Returns:
            None. The operation's lengths, status, placements, stitch points and shape are updated.

        Raises:
            ValueError: If the requested correspondence mode or normalized interval is invalid.
        """
        if part_module is None:
            import Part as part_module

        seam = getattr(obj, "Seam", None)
        piece_a = getattr(obj, "PieceA", None)
        piece_b = getattr(obj, "PieceB", None)
        if seam is None or piece_a is None or piece_b is None:
            obj.Status = "Incomplete"
            obj.LengthA = obj.LengthB = obj.LengthDifference = 0.0
            obj.StitchCount = 0
            obj.StitchPoints = []
            obj.Shape = part_module.Shape()
            return
        seam_status = str(getattr(seam, "Status", "Valid"))
        if seam_status != "Valid":
            obj.Status = "Invalid seam: " + seam_status
            obj.LengthA = obj.LengthB = obj.LengthDifference = 0.0
            obj.StitchCount = 0
            obj.StitchPoints = []
            obj.Shape = part_module.Shape()
            return
        try:
            la = _seam_length(piece_a, seam, "A", resolve_document_edge_fn=resolve_document_edge_fn)
            lb = _seam_length(piece_b, seam, "B", resolve_document_edge_fn=resolve_document_edge_fn)
        except (ChangedEdgeReference, MissingEdgeReference) as exc:
            obj.Status = f"Invalid seam: {exc}"
            obj.LengthA = obj.LengthB = obj.LengthDifference = 0.0
            obj.StitchCount = 0
            obj.StitchPoints = []
            obj.Shape = part_module.Shape()
            return
        obj.LengthA, obj.LengthB = la, lb
        obj.LengthDifference = abs(la - lb)

        relative_tolerance = max(0.0, min(0.999999, float(getattr(obj, "RelativeTolerance", 0.05))))
        correspondence = analyze_correspondence(
            la,
            lb,
            float(getattr(seam, "StartA", 0.0)),
            float(getattr(seam, "EndA", 1.0)),
            float(getattr(seam, "StartB", 0.0)),
            float(getattr(seam, "EndB", 1.0)),
            bool(getattr(seam, "ReversedB", False)),
            relative_tolerance,
        )
        if hasattr(obj, "CorrespondenceStatus"):
            obj.CorrespondenceStatus = correspondence.status
        if hasattr(obj, "CorrespondenceMessage"):
            obj.CorrespondenceMessage = correspondence.message
        if hasattr(obj, "CorrespondenceRecovery"):
            obj.CorrespondenceRecovery = correspondence.recovery
        if hasattr(obj, "CorrespondenceSeverity"):
            obj.CorrespondenceSeverity = correspondence.severity

        obj.StitchCount = max(2, int(obj.Stitches))
        obj.Status = correspondence_status_label(correspondence)
        if hasattr(obj, "SeamId"):
            obj.SeamId = str(getattr(seam, "SeamId", "") or "")
        if hasattr(obj, "ReversedB"):
            obj.ReversedB = bool(getattr(seam, "ReversedB", False))
        if hasattr(obj, "Alignment"):
            obj.Alignment = str(getattr(seam, "Alignment", "endpoints"))
        if hasattr(obj, "StitchGroup"):
            obj.StitchGroup = str(
                getattr(seam, "StitchGroup", "")
                or getattr(seam, "SeamId", "")
                or getattr(seam, "Name", "")
            )
        pairs = _seam_correspondence(
            piece_a,
            piece_b,
            seam,
            obj.StitchCount,
            getattr(obj, "Alignment", "endpoints"),
            vector_factory=vector_factory,
            resolve_document_edge_fn=resolve_document_edge_fn,
        )
        obj.AssemblyPlacementB = _alignment_placement(
            piece_a,
            piece_b,
            seam,
            app_module=app_module,
            vector_factory=vector_factory,
            resolve_document_edge_fn=resolve_document_edge_fn,
        )
        obj.StitchPoints = []
        for pa, pb in pairs:
            obj.StitchPoints.append(
                f"{pa.x:.6f},{pa.y:.6f},{pa.z:.6f}|{pb.x:.6f},{pb.y:.6f},{pb.z:.6f}"
            )
        obj.Shape = part_module.makeCompound(
            [
                part_module.makePolygon([p for p, _ in pairs]),
                part_module.makePolygon([p for _, p in pairs]),
            ]
        )


def add_sewing_operation(
    doc: _FreeCADDocument,
    seam: object,
    piece_a: object,
    piece_b: object,
    name: str = "SewingOperation",
) -> _SewingFeature:
    """Add the requested sewing operation data."""
    obj = doc.addObject("Part::FeaturePython", name)
    obj.Label = name
    obj.addProperty("App::PropertyString", "SewingType", "Sewing").SewingType = "SewingOperation"
    obj.addProperty("App::PropertyLink", "Seam", "Sewing").Seam = seam
    obj.addProperty("App::PropertyString", "SeamId", "Sewing").SeamId = str(
        getattr(seam, "SeamId", "") or ""
    )
    obj.addProperty("App::PropertyLink", "PieceA", "Sewing").PieceA = piece_a
    obj.addProperty("App::PropertyLink", "PieceB", "Sewing").PieceB = piece_b
    obj.addProperty("App::PropertyString", "StitchGroup", "Sewing").StitchGroup = str(
        getattr(seam, "StitchGroup", "") or getattr(seam, "SeamId", "") or getattr(seam, "Name", "")
    )
    obj.addProperty("App::PropertyEnumeration", "Alignment", "Sewing").Alignment = [
        "endpoints",
        "uniform",
    ]
    obj.Alignment = str(getattr(seam, "Alignment", "endpoints"))
    obj.addProperty("App::PropertyBool", "ReversedB", "Sewing").ReversedB = bool(
        getattr(seam, "ReversedB", False)
    )
    obj.addProperty(
        "App::PropertyPlacement", "AssemblyPlacementB", "Assembly"
    ).AssemblyPlacementB = piece_b.Placement
    obj.addProperty("App::PropertyLength", "Tolerance", "Validation").Tolerance = 0.5
    obj.addProperty(
        "App::PropertyFloat", "RelativeTolerance", "Validation"
    ).RelativeTolerance = 0.05
    obj.addProperty(
        "App::PropertyString", "CorrespondenceStatus", "Validation"
    ).CorrespondenceStatus = "valid"
    obj.addProperty(
        "App::PropertyString", "CorrespondenceMessage", "Validation"
    ).CorrespondenceMessage = "seam correspondence is valid"
    obj.addProperty(
        "App::PropertyString", "CorrespondenceRecovery", "Validation"
    ).CorrespondenceRecovery = "no repair required"
    obj.addProperty(
        "App::PropertyString", "CorrespondenceSeverity", "Validation"
    ).CorrespondenceSeverity = "info"
    obj.addProperty("App::PropertyInteger", "Stitches", "Stitching").Stitches = 8
    obj.addProperty("App::PropertyLength", "LengthA", "Validation").LengthA = 0
    obj.addProperty("App::PropertyLength", "LengthB", "Validation").LengthB = 0
    obj.addProperty("App::PropertyLength", "LengthDifference", "Validation").LengthDifference = 0
    obj.addProperty("App::PropertyInteger", "StitchCount", "Stitching").StitchCount = 8
    obj.setEditorMode("StitchCount", 1)
    obj.addProperty("App::PropertyStringList", "StitchPoints", "Stitching").StitchPoints = []
    obj.addProperty("App::PropertyString", "Status", "Validation").Status = "Incomplete"
    obj.setEditorMode("ReversedB", 1)
    obj.setEditorMode("Alignment", 1)
    obj.setEditorMode("StitchGroup", 1)
    obj.setEditorMode("AssemblyPlacementB", 1)
    obj.setEditorMode("CorrespondenceStatus", 1)
    obj.setEditorMode("CorrespondenceMessage", 1)
    obj.setEditorMode("CorrespondenceRecovery", 1)
    obj.setEditorMode("CorrespondenceSeverity", 1)
    proxy = SewingOperationProxy()
    obj.Proxy = proxy
    proxy.execute(obj)
    from freecad_cloth.common.GarmentDocument import link_garment_object

    link_garment_object(obj, "SewingOperation", doc)
    from freecad_cloth.sewing.SewingView import apply_seam_colors

    apply_seam_colors(doc.Objects)
    return obj
