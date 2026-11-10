# Copyright (C) 2026 FreeCAD Cloth contributors
"""3D surface authoring bridge for Cloth Pattern.

The surface pen is intentionally an authoring frontend, not a second pattern
editor. It records a temporary surface stroke on a visible FreeCAD target and
can extract a sufficiently planar patch into a normal native Sketcher-backed
PatternPiece.

The MVP fail-closes when the sampled patch cannot be represented by a single
2D plane without exceeding the configured deviation tolerance. A future
surface-parameterization backend can replace the flattening helper without
changing the viewport or PatternPiece authority boundaries.
"""

from __future__ import annotations

import contextlib
import json
import math
from itertools import starmap
from typing import TYPE_CHECKING

import numpy as np
from pydantic.dataclasses import dataclass as pydantic_dataclass
from shapely.geometry import LinearRing

from freecad_cloth.shared.SourceSignature import source_signature

if TYPE_CHECKING:
    import collections.abc

Point3 = tuple[float, float, float]
Vector3 = Point3
Point2 = tuple[float, float]
DEFAULT_CLOSE_DISTANCE_MM = 6.0


def _as_point3(value) -> Point3:
    """Normalize a FreeCAD vector-like value into a finite three-component tuple.

    Args:
        value: Iterable coordinate or object exposing X/Y/Z-style lowercase fields.

    Returns:
        Three floating-point coordinates in the source coordinate frame.
    """
    try:
        values = tuple(value)
        if len(values) >= 3:
            return tuple(float(v) for v in values[:3])
    except (TypeError, ValueError):
        pass
    return (float(value.x), float(value.y), float(value.z))


def _dot(a: Vector3, b: Vector3) -> float:
    """Calculate the scalar product of two three-dimensional vectors.

    Args:
        a: First vector.
        b: Second vector.

    Returns:
        Scalar dot product of the corresponding components.
    """
    return sum(float(x) * float(y) for x, y in zip(a, b, strict=False))


def _cross(a: Vector3, b: Vector3) -> Vector3:
    """Calculate the right-handed cross product of two three-dimensional vectors.

    Args:
        a: First vector.
        b: Second vector.

    Returns:
        Vector perpendicular to both inputs following right-hand orientation.
    """
    return (
        float(a[1]) * float(b[2]) - float(a[2]) * float(b[1]),
        float(a[2]) * float(b[0]) - float(a[0]) * float(b[2]),
        float(a[0]) * float(b[1]) - float(a[1]) * float(b[0]),
    )


def _sub(a: Point3, b: Point3) -> Vector3:
    """Subtract one 3D point from another to obtain a displacement vector.

    Args:
        a: Point at the destination of the displacement.
        b: Point at the origin of the displacement.

    Returns:
        Vector from point b to point a.
    """
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a: Point3, b: Vector3) -> Point3:
    """Translate a 3D point by a displacement vector.

    Args:
        a: Original point.
        b: Translation vector.

    Returns:
        Translated point in the same coordinate frame.
    """
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(a: Vector3, value: float) -> Vector3:
    """Multiply every component of a vector by a scalar.

    Args:
        a: Vector to scale.
        value: Scalar multiplier applied to all components.

    Returns:
        Scaled vector.
    """
    return (a[0] * value, a[1] * value, a[2] * value)


def _length(a: Vector3) -> float:
    """Calculate the Euclidean length of a three-dimensional vector.

    Args:
        a: Vector whose magnitude is measured.

    Returns:
        Non-negative Euclidean vector length.
    """
    return math.sqrt(_dot(a, a))


def _normalize(a: Vector3) -> Vector3:
    """Return a unit vector in the same direction as the input.

    Args:
        a: Nonzero vector to normalize.

    Returns:
        Unit-length vector with the input direction.

    Raises:
        ValueError: If the vector is too small to define a stable direction.
    """
    length = _length(a)
    if length <= 1e-12:
        msg = "surface points do not define a usable direction"
        raise ValueError(msg)
    return _scale(a, 1.0 / length)


def _centroid(points: collections.abc.Sequence[Point3]) -> Point3:
    """Compute a 3D centroid with NumPy's vectorized mean.

    Args:
        points: Non-empty finite 3D coordinates.

    Returns:
        The component-wise arithmetic mean of the supplied coordinates.

    Raises:
        ValueError: If no points are supplied.
    """
    if not points:
        msg = "at least one point is required"
        raise ValueError(msg)
    mean = np.mean(np.asarray(points, dtype=np.float64), axis=0)
    return (float(mean[0]), float(mean[1]), float(mean[2]))


def polygon_area_2d(points: collections.abc.Sequence[Point2]) -> float:
    """Compute the signed area enclosed by an ordered 2D polygon boundary.

    Args:
        points: Ordered polygon vertices in millimetres, without a required closing point.

    Returns:
        Signed area in square millimetres; positive values indicate counter-clockwise
        winding and fewer than three points produce zero.
    """
    if len(points) < 3:
        return 0.0
    coordinates = np.asarray(points, dtype=np.float64)
    following = np.roll(coordinates, -1, axis=0)
    cross_terms = coordinates[:, 0] * following[:, 1] - following[:, 0] * coordinates[:, 1]
    return 0.5 * float(np.sum(cross_terms, dtype=np.float64))


def polygon_self_intersects(points: collections.abc.Sequence[Point2]) -> bool:
    """Return whether the closed polygon ring intersects itself.

    Shapely delegates the exact segment-intersection predicate to GEOS, avoiding
    a quadratic Python loop and keeping adjacent-edge endpoint handling in one
    geometry-library implementation.

    Args:
        points: Ordered polygon boundary points, without a required closing duplicate.

    Returns:
        Whether the corresponding closed ring is not simple.
    """
    if len(points) < 4:
        return False
    return not bool(LinearRing(points).is_simple)


def simplify_polyline(
    points: collections.abc.Sequence[Point3], tolerance_mm: float = 1.0
) -> tuple[Point3, ...]:
    """Simplify a spatial polyline with the recursive Ramer-Douglas-Peucker algorithm.

    Args:
        points: Ordered 3D samples along the authored surface stroke.
        tolerance_mm: Maximum perpendicular deviation retained in millimetres.

    Returns:
        Simplified ordered points while preserving the first and last samples.
    """
    values = tuple(_as_point3(point) for point in points)
    if len(values) <= 2:
        return values
    tolerance = max(0.0, float(tolerance_mm))
    if tolerance <= 1e-12:
        return values

    def perpendicular_distance(point: Point3, start: Point3, end: Point3) -> float:
        """Measure the shortest distance from a point to a finite segment axis.

        Args:
            point: Query coordinate.
            start: First segment endpoint.
            end: Second segment endpoint.

        Returns:
            Distance from the query point to the segment, including degenerate cases.
        """
        axis = _sub(end, start)
        span = _length(axis)
        if span <= 1e-12:
            return _length(_sub(point, start))
        projection = _add(start, _scale(axis, _dot(_sub(point, start), axis) / (span * span)))
        return _length(_sub(point, projection))

    def rdp(items: collections.abc.Sequence[Point3]) -> tuple[Point3, ...]:
        """Retain endpoints and any sample exceeding the current deviation tolerance.

        Args:
            items: Ordered sub-sequence of source polyline coordinates.

        Returns:
            Simplified sub-sequence preserving its first and last coordinates.
        """
        if len(items) <= 2:
            return tuple(items)
        start, end = items[0], items[-1]
        farthest_index = -1
        farthest_distance = tolerance
        for index in range(1, len(items) - 1):
            distance = perpendicular_distance(items[index], start, end)
            if distance > farthest_distance:
                farthest_distance = distance
                farthest_index = index
        if farthest_index < 0:
            return (start, end)
        left = rdp(items[: farthest_index + 1])
        right = rdp(items[farthest_index:])
        return left[:-1] + right

    return rdp(values)


def surface_segments_from_anchor_kinds(
    points: collections.abc.Sequence[Point2],
    kinds: collections.abc.Sequence[str],
) -> tuple[tuple[str, tuple[Point2, ...]], ...]:
    """Build line and B-spline segments from corner points and curve-through points.

    A curve point between two corners makes their connecting boundary segment a
    B-spline interpolating both corners and the curve points. Consecutive corners
    remain straight lines, so authored sharp corners are preserved.

    Args:
        points: Ordered projected points around the surface boundary.
        kinds: Matching point-kind values, each either corner or curve.

    Returns:
        Ordered segment-kind and point-sequence pairs for native sketch geometry.

    Raises:
        ValueError: If there are too few points/corners or point kinds are invalid.
    """
    values = tuple((float(point[0]), float(point[1])) for point in points)
    point_kinds = tuple(str(kind).lower() for kind in kinds)
    if len(values) < 3:
        msg = "surface boundary needs at least three points"
        raise ValueError(msg)
    if len(point_kinds) != len(values):
        msg = "surface boundary point types do not match the point count"
        raise ValueError(msg)
    if any(kind not in {"corner", "curve"} for kind in point_kinds):
        msg = "surface boundary point type must be corner or curve"
        raise ValueError(msg)
    corners = [index for index, kind in enumerate(point_kinds) if kind == "corner"]
    if len(corners) < 3:
        msg = "surface boundary needs at least three corner points"
        raise ValueError(msg)

    segments = []
    count = len(values)
    for corner_index, start_index in enumerate(corners):
        end_index = corners[(corner_index + 1) % len(corners)]
        segment_points = [values[start_index]]
        interior_indices = []
        index = (start_index + 1) % count
        while index != end_index:
            segment_points.append(values[index])
            interior_indices.append(index)
            index = (index + 1) % count
        segment_points.append(values[end_index])
        if any(point_kinds[index] == "curve" for index in interior_indices):
            # Projection can collapse distinct 3D anchors onto the same 2D point.
            compact = []
            for point in segment_points:
                if not compact or math.dist(point, compact[-1]) > 1e-7:
                    compact.append(point)
            if len(compact) < 3:
                segments.append(("line", (values[start_index], values[end_index])))
            else:
                segments.append(("bspline", tuple(compact)))
        else:
            segments.append(("line", (values[start_index], values[end_index])))
    return tuple(segments)


@pydantic_dataclass(frozen=True)
class SurfaceAnchor:
    """A picked target-space point with its surface normal and authoring intent.

    Corner points create straight segments unless curve points occur before the
    next corner. Curve points are interpolated by a native B-spline between their
    neighboring corners. The default keeps older saved drafts compatible.
    """

    point: Point3
    normal: Vector3
    kind: str = "corner"

    def to_json(self) -> dict:
        """Serialize this surface anchor for persistent document storage.

        Returns:
            JSON-compatible mapping containing rounded point, normal, and authoring kind.
        """
        return {
            "point": [round(float(value), 6) for value in self.point],
            "normal": [round(float(value), 6) for value in self.normal],
            "kind": self.kind,
        }

    @classmethod
    def from_json(cls, value: dict) -> SurfaceAnchor:
        """Restore a surface anchor from its serialized mapping.

        Args:
            value: Serialized mapping containing point, normal, and explicit kind fields.

        Returns:
            Validated surface anchor in world coordinates.

        Raises:
            ValueError: If the kind field is missing or names an unsupported point type.
        """
        if "kind" not in value:
            msg = "surface anchor JSON requires an explicit point type"
            raise ValueError(msg)
        kind = str(value["kind"]).lower()
        if kind not in {"corner", "curve"}:
            msg = f"unsupported surface anchor point type: {kind}"
            raise ValueError(msg)
        return cls(_as_point3(value["point"]), _as_point3(value["normal"]), kind)


@pydantic_dataclass(frozen=True)
class FlattenedSurfacePatch:
    """2D result of the bounded MVP surface-to-plane projection."""

    points: tuple[Point2, ...]
    centroid: Point3
    normal: Vector3
    max_deviation_mm: float

    def validate(self, tolerance_mm: float) -> FlattenedSurfacePatch:
        """Validate topology, area, and the maximum allowed out-of-plane deviation.

        Args:
            tolerance_mm: Maximum accepted deviation from the fitted projection plane.

        Returns:
            This validated flattened patch for convenient validation chaining.

        Raises:
            ValueError: If the boundary is too small, self-intersects, has negligible
                area, or exceeds the permitted planar deviation.
        """
        if len(self.points) < 3:
            msg = "surface patch needs at least three distinct points"
            raise ValueError(msg)
        if polygon_self_intersects(self.points):
            msg = "surface patch self-intersects after flattening"
            raise ValueError(msg)
        if abs(polygon_area_2d(self.points)) <= 1e-6:
            msg = "surface patch has negligible 2D area"
            raise ValueError(msg)
        limit = max(0.0, float(tolerance_mm))
        if self.max_deviation_mm > limit + 1e-9:
            msg = (
                "surface patch is too curved for the bounded planar MVP: "
                f"{self.max_deviation_mm:.2f} mm deviation exceeds {limit:.2f} mm tolerance"
            )
            raise ValueError(msg)
        return self


def flatten_surface_patch(
    points: collections.abc.Sequence[Point3],
    tolerance_mm: float = 8.0,
) -> FlattenedSurfacePatch:
    """Project a sampled closed surface boundary onto a deterministic best local plane.

    The plane is oriented from a deterministic local boundary normal. This is not a
    general mesh parameterization; the explicit deviation test prevents silently
    turning a strongly curved region into a misleading flat pattern.

    Args:
        points: Ordered world-space samples around the proposed surface boundary.
        tolerance_mm: Maximum accepted planar deviation in millimetres.

    Returns:
        Validated planar points together with the source centroid, normal, and deviation.

    Raises:
        ValueError: If fewer than three samples exist or no stable projection plane
            can be formed, or when the flattened boundary fails validation.
    """
    values = tuple(_as_point3(point) for point in points)
    if len(values) < 3:
        msg = "surface patch needs at least three points"
        raise ValueError(msg)
    coordinate_array = np.asarray(values, dtype=np.float64)
    center = _centroid(values)

    # Use the strongest non-collinear local triangle instead of a polygon Newell
    # sum. A self-intersecting boundary may have a zero Newell normal even though
    # its individual segments still define a usable projection plane; validation
    # should then report the actual self-intersection rather than a misleading
    # "no direction" error.
    origin = coordinate_array[0]
    relative_to_origin = coordinate_array - origin
    candidate_normals = np.cross(relative_to_origin[1:-1], relative_to_origin[2:])
    candidate_lengths = np.linalg.norm(candidate_normals, axis=1)
    best_normal = candidate_normals[int(np.argmax(candidate_lengths))]
    normal = _normalize(tuple(float(value) for value in best_normal))

    # Prefer the longest centered edge as the local U axis to make the result
    # deterministic while preserving the user's dominant drawing direction.
    edges = np.roll(coordinate_array, -1, axis=0) - coordinate_array
    normal_array = np.asarray(normal, dtype=np.float64)
    projected_edges = edges - np.outer(edges @ normal_array, normal_array)
    projected_lengths = np.linalg.norm(projected_edges, axis=1)
    u = _normalize(
        tuple(float(value) for value in projected_edges[int(np.argmax(projected_lengths))])
    )
    v = _normalize(_cross(normal, u))

    relative = coordinate_array - np.asarray(center, dtype=np.float64)
    u_coordinates = relative @ np.asarray(u, dtype=np.float64)
    v_coordinates = relative @ np.asarray(v, dtype=np.float64)
    projected = np.column_stack((u_coordinates, v_coordinates))
    points_2d = tuple((round(float(point[0]), 6), round(float(point[1]), 6)) for point in projected)
    max_deviation = float(np.max(np.abs(relative @ normal_array)))

    patch = FlattenedSurfacePatch(points_2d, center, normal, max_deviation)
    return patch.validate(tolerance_mm)


def _translate_points_to_positive_coordinates(
    points: collections.abc.Sequence[Point2],
) -> list[Point2]:
    """Translate a 2D point cloud to non-negative coordinates with NumPy.

    Args:
        points: Coordinates to translate without changing relative geometry.

    Returns:
        Points shifted so each coordinate's minimum is zero, rounded to 1e-6.
    """
    coordinates = np.asarray(points, dtype=np.float64)
    minimums = np.min(coordinates, axis=0)
    shifted = np.round(coordinates - minimums, decimals=6)
    return [(float(point[0]), float(point[1])) for point in shifted]


def _target_source(target):
    """Return the underlying geometry object linked by a surface target wrapper.

    Args:
        target: Native drape/target object, possibly wrapping a source feature.

    Returns:
        Linked source feature when present; otherwise the original target.
    """
    source = getattr(target, "SourceObject", None)
    return source if source is not None else target


def _target_signature(target) -> str:
    """Build a stable geometry signature used to detect stale surface drafts.

    Args:
        target: Surface target or wrapper whose source geometry is recorded.

    Returns:
        String representation of the source geometry signature, falling back to
        the target's stable object name when geometry cannot be inspected.
    """
    source = _target_source(target)
    try:
        return repr(
            source_signature(
                source,
                float(getattr(target, "CollisionDeflection", 1.0)),
                float(getattr(target, "CollisionThickness", 0.0)),
            )
        )
    except (AttributeError, TypeError, ValueError, RuntimeError):
        return str(getattr(target, "Name", ""))


def _surface_target_from_document(doc, Gui):
    """Resolve the selected or first available mannequin/drape target in a document.

    Args:
        doc: Active FreeCAD document containing candidate target objects.
        Gui: FreeCAD GUI module used to inspect the current selection.

    Returns:
        Pair of target wrapper and source geometry, or (None, None) when absent.
    """
    selection = tuple(Gui.Selection.getSelection()) if Gui is not None else ()
    for obj in selection:
        if str(getattr(obj, "TargetType", "")) in {"Mannequin", "FreeCAD Geometry"}:
            source = getattr(obj, "SourceObject", None)
            if source is not None:
                return obj, source
        if str(getattr(obj, "AvatarType", "")) == "ClothAvatar":
            return obj, obj
    for obj in getattr(doc, "Objects", ()):
        if str(getattr(obj, "TargetType", "")) in {"Mannequin", "FreeCAD Geometry"}:
            source = getattr(obj, "SourceObject", None)
            if source is not None:
                return obj, source
    for obj in getattr(doc, "Objects", ()):
        if str(getattr(obj, "AvatarType", "")) == "ClothAvatar":
            return obj, obj
    return None, None


def _hit_matches_target(view, x: int, y: int, target_source) -> bool:
    """Guard surface picking against unrelated visible geometry.

    Args:
        view: Active FreeCAD view used for object-info lookup.
        x: Horizontal viewport pixel coordinate.
        y: Vertical viewport pixel coordinate.
        target_source: Source object expected to receive the surface pick.

    Returns:
        Whether the pixel belongs to the intended target; unknown hits are allowed.
    """
    try:
        info = view.getObjectInfo(int(x), int(y))
    except (AttributeError, TypeError, ValueError, RuntimeError):
        info = None
    if not info:
        return True
    target_name = str(getattr(target_source, "Name", ""))
    target_label = str(getattr(target_source, "Label", ""))
    encoded = repr(info)
    return bool(target_name and target_name in encoded) or bool(
        target_label and target_label in encoded
    )


def pick_surface_point(view, x: int, y: int, target_source) -> SurfaceAnchor | None:
    """Pick a world-space point and normal from the selected surface target.

    Args:
        view: Active FreeCAD 3D view exposing Coin picking methods.
        x: Horizontal viewport pixel coordinate.
        y: Vertical viewport pixel coordinate.
        target_source: Source geometry that must own the pick.

    Returns:
        Surface anchor at the picked point, or None when the hit cannot be resolved.
    """
    if not _hit_matches_target(view, x, y, target_source):
        return None
    viewer_factory = getattr(view, "getViewer", None)
    if not callable(viewer_factory):
        return None
    viewer = viewer_factory()
    picker = getattr(viewer, "pickPoint", None)
    if not callable(picker):
        return None
    try:
        picked = picker((int(x), int(y)))
    except (TypeError, ValueError, RuntimeError):
        try:
            picked = picker(
                (
                    int(x),
                    int(y),
                )
            )
        except (TypeError, ValueError, RuntimeError):
            return None
    if picked is None:
        return None
    point_getter = getattr(picked, "getPoint", None)
    normal_getter = getattr(picked, "getNormal", None)
    if not callable(point_getter) or not callable(normal_getter):
        return None
    try:
        point = _as_point3(point_getter())
        normal = _normalize(_as_point3(normal_getter()))
    except (TypeError, ValueError, RuntimeError):
        return None
    return SurfaceAnchor(point, normal)


def _append_anchor(
    anchors: list[SurfaceAnchor],
    anchor: SurfaceAnchor,
    minimum_spacing_mm: float,
) -> bool:
    """Append an anchor unless it duplicates the most recent stroke sample.

    Args:
        anchors: Mutable ordered anchor list receiving the new sample.
        anchor: Surface point and normal to append.
        minimum_spacing_mm: Minimum spatial separation required between consecutive points.

    Returns:
        Whether the anchor was appended.
    """
    if anchors and _length(_sub(anchor.point, anchors[-1].point)) < float(minimum_spacing_mm):
        return False
    anchors.append(anchor)
    return True


def surface_stroke_can_finish(
    anchors: collections.abc.Sequence[SurfaceAnchor],
    tolerance_mm: float = DEFAULT_CLOSE_DISTANCE_MM,
) -> bool:
    """Check that a stroke contains a valid three-point boundary and a closing sample.

    Args:
        anchors: Ordered world-space anchors including the final closure sample.
        tolerance_mm: Maximum distance between the last and first sample in millimetres.

    Returns:
        Whether at least three unique boundary points exist and the final sample
        lies within the closure tolerance.
    """
    values = tuple(anchors)
    if len(values) < 4:
        return False
    boundary = values[:-1]
    unique = {tuple(round(float(value), 6) for value in anchor.point) for anchor in boundary}
    if len(unique) < 3:
        return False
    limit = max(0.0, float(tolerance_mm))
    return _length(_sub(values[-1].point, values[0].point)) <= limit + 1e-9


def close_surface_stroke(
    anchors: collections.abc.Sequence[SurfaceAnchor],
    tolerance_mm: float = DEFAULT_CLOSE_DISTANCE_MM,
) -> tuple[SurfaceAnchor, ...]:
    """Validate and normalize a closed surface boundary.

    Args:
        anchors: Ordered boundary anchors followed by a sample near the first point.
        tolerance_mm: Maximum allowed endpoint gap in millimetres.

    Returns:
        Boundary anchors without the redundant closing sample.

    Raises:
        ValueError: If closure is too distant or fewer than three distinct boundary
            points remain after removing the closing sample.
    """
    values = tuple(anchors)
    if len(values) < 4:
        msg = "surface boundary needs at least three distinct points and a closing sample"
        raise ValueError(msg)
    limit = max(0.0, float(tolerance_mm))
    distance = _length(_sub(values[-1].point, values[0].point))
    if distance > limit + 1e-9:
        msg = (
            "surface boundary is open; return to the first surface point "
            f"within {limit:.1f} mm before finishing (current gap: {distance:.1f} mm)"
        )
        raise ValueError(msg)
    boundary = values[:-1]
    unique = {tuple(round(float(value), 6) for value in anchor.point) for anchor in boundary}
    if len(unique) < 3:
        msg = "surface boundary needs at least three distinct points"
        raise ValueError(msg)
    return boundary


def create_surface_pen_object(
    doc, target, anchors: collections.abc.Sequence[SurfaceAnchor], label="3D Surface Draft"
):
    """Persist a finished surface draft as a rebuildable authoring object.

    Args:
        doc: FreeCAD document that owns the new draft feature.
        target: Drape/target object whose source geometry is being traced.
        anchors: Ordered surface anchors describing a closed boundary.
        label: User-visible label assigned to the persistent draft object.

    Returns:
        Native Part feature storing the serialized anchors and target provenance.
    """
    import FreeCAD as App
    import Part

    values = close_surface_stroke(anchors)
    stored_values = (*values, values[0])
    obj = doc.addObject("Part::FeaturePython", doc.getUniqueObjectName("SurfacePatternDraft"))
    obj.Label = label
    obj.addProperty(
        "App::PropertyString", "AuthoringType", "3D Pattern"
    ).AuthoringType = "ClothPattern.SurfacePen"
    obj.addProperty("App::PropertyLinkGlobal", "Target", "3D Pattern").Target = target
    obj.addProperty(
        "App::PropertyString", "TargetSignature", "3D Pattern"
    ).TargetSignature = _target_signature(target)
    obj.addProperty("App::PropertyString", "AnchorsJSON", "3D Pattern").AnchorsJSON = json.dumps(
        [anchor.to_json() for anchor in stored_values],
        sort_keys=True,
        separators=(",", ":"),
    )
    obj.addProperty("App::PropertyString", "Status", "State").Status = "Surface draft"
    obj.addProperty(
        "App::PropertyString", "FlatteningMode", "State"
    ).FlatteningMode = "PlanarProjectionMVP"
    obj.addProperty("App::PropertyLength", "PlanarTolerance", "State").PlanarTolerance = 8.0
    obj.addProperty("App::PropertyLength", "MaxDeviation", "State").MaxDeviation = 0.0
    obj.addProperty(
        "App::PropertyLength", "ClosureTolerance", "State"
    ).ClosureTolerance = DEFAULT_CLOSE_DISTANCE_MM
    points = [App.Vector(*anchor.point) for anchor in values]
    points.append(points[0])
    obj.Shape = Part.makePolygon(points)
    return obj


def _add_surface_provenance(piece, surface_draft):
    """Link an extracted PatternPiece back to its persistent surface draft.

    Args:
        piece: Native PatternPiece document object receiving provenance properties.
        surface_draft: Source draft feature retained for audit and re-extraction.
    """
    if "SurfaceDraft" not in piece.PropertiesList:
        piece.addProperty("App::PropertyLinkGlobal", "SurfaceDraft", "3D Authoring")
    piece.SurfaceDraft = surface_draft
    if "SurfaceAuthoring" not in piece.PropertiesList:
        piece.addProperty("App::PropertyString", "SurfaceAuthoring", "3D Authoring")
    piece.SurfaceAuthoring = "ClothPattern.SurfacePen"


def extract_surface_draft_to_pattern(surface_draft, tolerance_mm=8.0, name=None):
    """Create a native Sketcher-backed PatternPiece from a persisted surface draft.

    Args:
        surface_draft: Persistent Surface Pen feature containing target and anchor data.
        tolerance_mm: Maximum permitted planar deviation for extraction, in millimetres.
        name: Optional name assigned to the generated PatternPiece.

    Raises:
        ValueError: If target provenance is stale, anchor data is malformed, no active
            document exists, or the stroke cannot be flattened within tolerance.
    """
    import FreeCAD as App

    target = getattr(surface_draft, "Target", None)
    if target is None:
        msg = "surface draft has no target"
        raise ValueError(msg)
    expected = str(getattr(surface_draft, "TargetSignature", ""))
    if expected and expected != _target_signature(target):
        surface_draft.Status = "Stale surface target"
        msg = "surface draft target changed; redraw the surface before extraction"
        raise ValueError(msg)
    try:
        anchors = tuple(
            SurfaceAnchor.from_json(value)
            for value in json.loads(str(getattr(surface_draft, "AnchorsJSON", "[]")))
        )
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        msg = "surface draft contains invalid anchor data"
        raise ValueError(msg) from exc
    closure_tolerance = float(getattr(surface_draft, "ClosureTolerance", DEFAULT_CLOSE_DISTANCE_MM))
    anchors = close_surface_stroke(anchors, closure_tolerance)
    patch = flatten_surface_patch([anchor.point for anchor in anchors], tolerance_mm)
    surface_draft.PlanarTolerance = float(tolerance_mm)
    surface_draft.MaxDeviation = float(patch.max_deviation_mm)
    from freecad_cloth.pattern.PatternModel import PatternPiece
    from freecad_cloth.pattern.PatternObjects import add_pattern_piece
    from freecad_cloth.pattern.PatternSketch import create_sketch_for_piece

    doc = App.ActiveDocument
    if doc is None:
        msg = "open a FreeCAD document before extracting a pattern"
        raise ValueError(msg)
    existing_count = len(
        [obj for obj in doc.Objects if getattr(obj, "PatternType", "") == "PatternPiece"]
    )
    piece_name = str(name or f"Surface Piece {existing_count + 1}")
    piece_id = f"pattern-piece-surface-{existing_count + 1}"
    # Translate the flattened polygon to positive document coordinates without
    # changing its geometry. This keeps the default Sketcher view convenient.
    shifted = _translate_points_to_positive_coordinates(patch.points)
    segments = surface_segments_from_anchor_kinds(shifted, [anchor.kind for anchor in anchors])
    pattern = PatternPiece(piece_name, shifted, id=piece_id)
    obj = add_pattern_piece(doc, pattern)
    sketch = create_sketch_for_piece(pattern, doc, geometry_segments=segments)
    obj.GeometryMode = "Sketch"
    _add_surface_provenance(obj, surface_draft)
    surface_draft.Visibility = False
    sketch.Visibility = True
    surface_draft.Status = "Extracted"
    doc.recompute()
    return obj


def _surface_stroke_object(doc, target, anchors):
    """Create the persistent Part feature used to store a transient stroke.

    Args:
        doc: FreeCAD document that owns the draft.
        target: Surface target whose geometry was sampled.
        anchors: Ordered surface anchors captured during the stroke.

    Returns:
        Native Surface Pen draft object with serialized anchor and target metadata.
    """
    return create_surface_pen_object(doc, target, anchors)


class SurfacePenController:
    """Interactive viewport controller for the Cloth 3D Pattern Pen."""

    SAMPLE_PIXEL_THRESHOLD = 4.0
    SAMPLE_DISTANCE_MM = 3.0
    CLOSE_DISTANCE_MM = DEFAULT_CLOSE_DISTANCE_MM
    OVERLAY_OFFSET_MM = 0.25

    def __init__(self, target, target_source, status_callback=None):
        """Initialize a viewport controller for one surface target.

        Args:
            target: Persistent target wrapper used for draft provenance.
            target_source: Native source geometry accepted by the picker.
            status_callback: Optional callback receiving user-facing status messages.
        """
        self.App, self.Gui = self._modules()
        self.target = target
        self.target_source = target_source
        self.status_callback = status_callback or (lambda _message: None)
        self.view = None
        self.anchors: list[SurfaceAnchor] = []
        self.input_mode = "point"
        self.point_kind = "corner"
        self._drawing = False
        self._last_screen = None
        self._mouse_callback = None
        self._location_callback = None
        self._overlay = None

    @staticmethod
    def _modules():
        """Import the FreeCAD application and GUI modules at controller startup.

        Returns:
            Application and GUI module objects required by the viewport controller.
        """
        import FreeCAD as App
        import FreeCADGui as Gui

        return App, Gui

    def _status(self, message):
        """Forward a status message to the task panel when a callback is installed.

        Args:
            message: User-facing description of the current stroke state.
        """
        self.status_callback(str(message))

    @property
    def can_finish(self) -> bool:
        """Return whether this mode has enough input to finish safely.

        Returns:
            Whether the current reference points or closed boundary satisfy the
            minimum input requirements for the selected authoring mode.
        """
        if self.input_mode == "references":
            return len(self.anchors) >= 3
        if not surface_stroke_can_finish(self.anchors, self.CLOSE_DISTANCE_MM):
            return False
        if self.input_mode == "point":
            return sum(anchor.kind == "corner" for anchor in self.anchors[:-1]) >= 3
        return True

    def set_input_mode(self, value: str) -> None:
        """Switch between point placement, freehand trace, and reference-point modes."""
        label = str(value).lower()
        if "freehand" in label:
            mode = "freehand"
        elif "reference" in label:
            mode = "references"
        else:
            mode = "point"
        self.input_mode = mode
        self._drawing = False
        self._last_screen = None
        self._status(self._stroke_status())

    def set_point_kind(self, value: str) -> None:
        """Choose whether the next placed anchor is a corner or curve-through point."""
        self.point_kind = "curve" if "curve" in str(value).lower() else "corner"
        self._status(self._stroke_status())

    def _stroke_status(self) -> str:
        """Describe the boundary closure, point count, and current authoring mode.

        Returns:
            User-facing status text describing the current stroke and next action.
        """
        if not self.anchors:
            if self.input_mode == "point":
                return (
                    "Point placement: click the target to add corners. Choose Curve point "
                    "to create a smooth segment between neighboring corners."
                )
            if self.input_mode == "references":
                return (
                    "Reference points: click at least three locations around the intended "
                    "outline. Finish creates construction points in a native Sketcher sketch."
                )
            return "Freehand trace: drag on the selected surface. Release to lift and continue."
        if self.input_mode == "references":
            return (
                f"Reference points: {len(self.anchors)} placed. Add points around the intended "
                "outline; finish when at least three points define a usable planar patch."
            )
        distance = _length(_sub(self.anchors[-1].point, self.anchors[0].point))
        boundary_count = len(self.anchors) - 1
        if surface_stroke_can_finish(self.anchors, self.CLOSE_DISTANCE_MM):
            if self.input_mode == "point":
                corners = sum(anchor.kind == "corner" for anchor in self.anchors[:-1])
                if corners < 3:
                    return (
                        f"Boundary closed, but only {corners} corner points are placed. "
                        "Add at least three corners before finishing."
                    )
            return (
                f"Boundary closed: {boundary_count} points; gap {distance:.1f} mm. "
                "Finish Stroke → Pattern is ready."
            )
        if len(self.anchors) < 4:
            return (
                f"Boundary: {len(self.anchors)} points. Add at least three distinct points, "
                f"then return within {self.CLOSE_DISTANCE_MM:.1f} mm of the start."
            )
        return (
            f"Boundary: {len(self.anchors)} points; endpoint gap {distance:.1f} mm. "
            f"Return within {self.CLOSE_DISTANCE_MM:.1f} mm of the first point to close."
        )

    def _pick(self, position):
        """Pick a surface anchor at a screen-space viewport location.

        Args:
            position: Horizontal and vertical viewport pixel coordinates.

        Returns:
            Picked target-space anchor, or None when no valid hit is available.
        """
        return pick_surface_point(self.view, int(position[0]), int(position[1]), self.target_source)

    def _update_overlay(self):
        """Refresh the transient Coin polyline that previews the current stroke."""
        if self.view is None:
            return
        try:
            from pivy import coin

            scene = self.view.getSceneGraph()
            if self._overlay is not None:
                scene.removeChild(self._overlay)
            self._overlay = coin.SoSeparator()
            coords = coin.SoCoordinate3()
            # Lift display geometry slightly above the picked surface to avoid
            # depth-buffer flicker. The persisted world-space anchors stay exact.
            points = [
                _add(anchor.point, _scale(anchor.normal, self.OVERLAY_OFFSET_MM))
                for anchor in self.anchors
            ]
            if len(points) >= 3 and _length(_sub(points[-1], points[0])) <= self.CLOSE_DISTANCE_MM:
                # Preview the closing edge as soon as the pointer returns near the
                # start. This is a viewport cue only; the stored anchors are unchanged.
                points.append(points[0])
            coords.point.setValues(
                0,
                len(points),
                list(starmap(coin.SbVec3f, points)),
            )
            line = coin.SoLineSet()
            line.numVertices.setValue(len(points))
            material = coin.SoBaseColor()
            material.rgb = (0.95, 0.55, 0.10)
            width = coin.SoDrawStyle()
            width.lineWidth = 4.0
            self._overlay.addChild(material)
            self._overlay.addChild(width)
            self._overlay.addChild(coords)
            self._overlay.addChild(line)
            scene.addChild(self._overlay)
        except (ImportError, AttributeError, RuntimeError, TypeError, ValueError):
            self._overlay = None

    def _event_position(self, info):
        """Extract a usable screen position from a FreeCAD viewport event mapping.

        Args:
            info: Event information mapping containing a Position pair.

        Returns:
            Floating-point screen coordinates, or None when the value is malformed.
        """
        value = info.get("Position", (0, 0))
        try:
            return float(value[0]), float(value[1])
        except (TypeError, ValueError, IndexError):
            return None

    def activate(self):
        """Install viewport callbacks and begin interactive surface drawing.

        Raises:
            RuntimeError: If no active FreeCAD document or 3D view is available.
        """
        if self.view is not None:
            return
        active = self.Gui.activeDocument()
        if active is None:
            msg = "an active FreeCAD document is required"
            raise RuntimeError(msg)
        self.view = active.activeView()
        if self.view is None:
            msg = "an active FreeCAD 3D view is required"
            raise RuntimeError(msg)
        self._mouse_callback = self.view.addEventCallback("SoMouseButtonEvent", self._mouse_event)
        self._location_callback = self.view.addEventCallback(
            "SoLocation2Event", self._location_event
        )
        self._status("3D Pattern Pen ready. " + self._stroke_status())

    def deactivate(self):
        """Remove viewport callbacks and discard transient drawing state."""
        if self.view is None:
            return
        try:
            if self._mouse_callback is not None:
                self.view.removeEventCallback("SoMouseButtonEvent", self._mouse_callback)
            if self._location_callback is not None:
                self.view.removeEventCallback("SoLocation2Event", self._location_callback)
            if self._overlay is not None:
                self.view.getSceneGraph().removeChild(self._overlay)
        except (AttributeError, RuntimeError):
            pass
        self._mouse_callback = None
        self._location_callback = None
        self._overlay = None
        self.view = None
        self._drawing = False
        self._last_screen = None

    def clear(self):
        """Clear the current stroke and remove its viewport overlay."""
        self.anchors.clear()
        self._drawing = False
        self._last_screen = None
        self._update_overlay()
        self._status("Surface stroke cleared. " + self._stroke_status())

    def _place_point(self, anchor: SurfaceAnchor) -> bool:
        """Append one deliberate boundary point and accept a near-start click as closure.

        Args:
            anchor: World-space anchor picked from the active target.

        Returns:
            Whether a new point was appended or the closure click was accepted.
        """
        placed = SurfaceAnchor(anchor.point, anchor.normal, self.point_kind)
        if (
            len(self.anchors) >= 3
            and _length(_sub(placed.point, self.anchors[0].point)) <= self.CLOSE_DISTANCE_MM
        ):
            self.anchors.append(placed)
            return True
        return _append_anchor(self.anchors, placed, self.SAMPLE_DISTANCE_MM)

    def _place_reference_point(self, anchor: SurfaceAnchor) -> bool:
        """Append one reference point without treating proximity to the start as closure.

        Args:
            anchor: World-space anchor selected for the construction-point sketch.

        Returns:
            Whether the anchor was appended after minimum-spacing validation.
        """
        placed = SurfaceAnchor(anchor.point, anchor.normal, "corner")
        return _append_anchor(self.anchors, placed, self.SAMPLE_DISTANCE_MM)

    def _mouse_event(self, info):
        """Handle press/release events for point, reference, and freehand modes.

        Args:
            info: FreeCAD Coin mouse event mapping with button, state, and position.
        """
        position = self._event_position(info)
        if position is None:
            return
        state = str(info.get("State", "")).upper()
        button = str(info.get("Button", "BUTTON1")).upper()
        if button not in {"BUTTON1", "LEFT"}:
            return
        if state == "DOWN":
            anchor = self._pick(position)
            if anchor is None:
                self._status("Pointer is not over the selected mannequin surface.")
                return
            if self.input_mode in {"point", "references"}:
                if self.input_mode == "references":
                    self._place_reference_point(anchor)
                else:
                    self._place_point(anchor)
                self._update_overlay()
                self._status(self._stroke_status())
                return
            self._drawing = True
            self._last_screen = position
            _append_anchor(self.anchors, anchor, self.SAMPLE_DISTANCE_MM)
            self._update_overlay()
            self._status(self._stroke_status())
        elif state == "UP":
            self._drawing = False
            self._last_screen = None
            self._status(self._stroke_status())

    def _location_event(self, info):
        """Sample additional target points while a freehand stroke is active.

        Args:
            info: FreeCAD Coin location event mapping containing screen position.
        """
        if not self._drawing:
            return
        position = self._event_position(info)
        if position is None:
            return
        if self._last_screen is not None:
            dx = position[0] - self._last_screen[0]
            dy = position[1] - self._last_screen[1]
            if math.hypot(dx, dy) < self.SAMPLE_PIXEL_THRESHOLD:
                return
        anchor = self._pick(position)
        if anchor is None:
            return
        if _append_anchor(self.anchors, anchor, self.SAMPLE_DISTANCE_MM):
            self._last_screen = position
            self._update_overlay()
            self._status(self._stroke_status())

    def _finish_reference_points(self, document: object, tolerance_mm: float) -> object:
        """Create a native Sketcher sketch containing flattened construction points.

        Args:
            document: Active FreeCAD document receiving the result sketch.
            tolerance_mm: Maximum permitted planar deviation of the reference points.

        Returns:
            Native Sketcher document object containing construction-point geometry.

        Raises:
            ValueError: If fewer than three points exist or the patch cannot be
                represented within the requested planar tolerance.
        """
        import Part

        if len(self.anchors) < 3:
            msg = "reference-point mode needs at least three points"
            raise ValueError(msg)
        patch = flatten_surface_patch([anchor.point for anchor in self.anchors], tolerance_mm)
        shifted = _translate_points_to_positive_coordinates(patch.points)
        sketch = document.addObject(
            "Sketcher::SketchObject",
            document.getUniqueObjectName("SurfaceReferencePoints"),
        )
        sketch.Label = "Surface Reference Points"
        sketch.addProperty("App::PropertyString", "SurfaceAuthoring", "3D Authoring")
        sketch.SurfaceAuthoring = "ClothPattern.SurfacePen.ReferencePoints"
        sketch.addProperty("App::PropertyLinkGlobal", "SurfaceTarget", "3D Authoring")
        sketch.SurfaceTarget = self.target
        sketch.addProperty("App::PropertyString", "SurfaceTargetSignature", "3D Authoring")
        sketch.SurfaceTargetSignature = _target_signature(self.target)
        sketch.addProperty("App::PropertyString", "SurfaceAnchorsJSON", "3D Authoring")
        sketch.SurfaceAnchorsJSON = json.dumps(
            [anchor.to_json() for anchor in self.anchors],
            sort_keys=True,
            separators=(",", ":"),
        )
        sketch.addProperty("App::PropertyLength", "PlanarTolerance", "3D Authoring")
        sketch.PlanarTolerance = float(tolerance_mm)
        sketch.addProperty("App::PropertyLength", "MaxDeviation", "3D Authoring")
        sketch.MaxDeviation = float(patch.max_deviation_mm)
        for x, y in shifted:
            sketch.addGeometry(Part.Point(self.App.Vector(x, y, 0)), True)
        document.recompute()
        self.clear()
        self._status(
            f"Created native Sketcher reference-point sketch with {len(shifted)} points. "
            "Connect the construction points with native Sketcher geometry."
        )
        return sketch

    def finish(self, tolerance_mm=8.0, name=None):
        """Finish the active Surface Pen mode and create its native Sketcher result.

        Args:
            tolerance_mm: Maximum accepted planar deviation in millimetres.
            name: Optional name assigned to the extracted PatternPiece.

        Raises:
            RuntimeError: If there is no active FreeCAD document.
            ValueError: If the stroke is open, too small, stale, or too curved for
                the requested planar representation.
        """
        if self._drawing:
            self._drawing = False
            self._last_screen = None
        document = self.App.ActiveDocument
        if document is None:
            msg = "an active document is required"
            raise RuntimeError(msg)
        if self.input_mode == "references":
            return self._finish_reference_points(document, tolerance_mm)
        closed = close_surface_stroke(self.anchors, self.CLOSE_DISTANCE_MM)
        if self.input_mode == "point":
            anchors = closed
        else:
            simplified = simplify_polyline([anchor.point for anchor in closed], 1.0)
            if len(simplified) < 3:
                msg = "surface stroke simplified to fewer than three points"
                raise ValueError(msg)
            by_point = {
                tuple(round(value, 6) for value in anchor.point): anchor for anchor in closed
            }
            anchors = tuple(
                by_point.get(tuple(round(value, 6) for value in point))
                or SurfaceAnchor(point, closed[min(index, len(closed) - 1)].normal)
                for index, point in enumerate(simplified)
            )
        # Validate the same bounded planar contract before any persistent object
        # is created. Extraction repeats the target-signature check.
        patch = flatten_surface_patch([anchor.point for anchor in anchors], tolerance_mm)
        # Retain the closing sample in persisted state: extraction repeats the
        # closure check on the serialized stroke before flattening it.
        draft_anchors = (*anchors, self.anchors[-1])
        draft = _surface_stroke_object(document, self.target, draft_anchors)
        draft.PlanarTolerance = float(tolerance_mm)
        draft.MaxDeviation = float(patch.max_deviation_mm)
        piece = extract_surface_draft_to_pattern(draft, tolerance_mm=tolerance_mm, name=name)
        self.clear()
        self._status(
            f"Created native Sketcher PatternPiece '{piece.Label}' "
            f"from a {len(anchors)}-point surface stroke."
        )
        return piece


class SurfacePenTaskPanel:
    """Small native FreeCAD task panel controlling the viewport pen."""

    def __init__(self, controller):
        """Build the Qt task panel controlling an active Surface Pen controller.

        Args:
            controller: Viewport controller whose current stroke is edited by the panel.
        """
        _App, _Gui, QtWidgets = self._modules()
        self.controller = controller
        self.form = QtWidgets.QWidget()
        outer = QtWidgets.QVBoxLayout(self.form)

        instructions = QtWidgets.QLabel(
            "<b>3D Pattern Pen</b><br>"
            "Point placement: click to add corners. A Curve point between two corners "
            "creates a smooth B-spline segment. Freehand trace remains available for "
            "drag-based sampling. Reference points creates construction points to connect in Sketcher."
        )
        instructions.setWordWrap(True)
        outer.addWidget(instructions)
        self.form.setMaximumWidth(380)

        controls = QtWidgets.QFormLayout()
        self.input_mode_combo = QtWidgets.QComboBox()
        self.input_mode_combo.addItems(["Point placement", "Freehand trace", "Reference points"])
        self.input_mode_combo.currentTextChanged.connect(self._input_mode_changed)
        controls.addRow("Input mode", self.input_mode_combo)

        self.point_kind_combo = QtWidgets.QComboBox()
        self.point_kind_combo.addItems(["Corner point", "Curve point"])
        self.point_kind_combo.setToolTip(
            "A curve point is interpolated between the neighboring corner points."
        )
        self.point_kind_combo.currentTextChanged.connect(self._point_kind_changed)
        controls.addRow("Point type", self.point_kind_combo)

        self.tolerance = QtWidgets.QDoubleSpinBox()
        self.tolerance.setRange(0.5, 100.0)
        self.tolerance.setDecimals(1)
        self.tolerance.setSuffix(" mm")
        self.tolerance.setValue(8.0)
        controls.addRow("Planar deviation limit", self.tolerance)
        outer.addLayout(controls)

        self.status = QtWidgets.QLabel("Waiting for surface input.")
        self.status.setWordWrap(True)
        outer.addWidget(self.status)

        buttons = QtWidgets.QHBoxLayout()
        self.finish_button = QtWidgets.QPushButton("Finish Stroke → Pattern")
        self.finish_button.clicked.connect(self.finish)
        self.clear_button = QtWidgets.QPushButton("Clear")
        self.clear_button.clicked.connect(self.controller.clear)
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        buttons.addWidget(self.finish_button)
        buttons.addWidget(self.clear_button)
        buttons.addWidget(self.cancel_button)
        outer.addLayout(buttons)
        self.controller.status_callback = self.update_status
        self._input_mode_changed(self.input_mode_combo.currentText())
        self._point_kind_changed(self.point_kind_combo.currentText())
        self.update_status(self.controller._stroke_status())

    def _input_mode_changed(self, value: str) -> None:
        """Switch between boundary authoring, freehand tracing, and reference points.

        Args:
            value: Visible combo-box label identifying the desired input mode.
        """
        self.controller.set_input_mode(value)
        self.point_kind_combo.setEnabled(self.controller.input_mode == "point")
        if self.controller.input_mode == "references":
            self.finish_button.setText("Create Sketcher Points")
        else:
            self.finish_button.setText("Finish Stroke → Pattern")

    def _point_kind_changed(self, value: str) -> None:
        """Set the kind assigned to the next point placed on the target.

        Args:
            value: Visible combo-box label selecting corner or curve point semantics.
        """
        self.controller.set_point_kind(value)

    def update_status(self, message: str) -> None:
        """Show drawing guidance and enable extraction only for a closable boundary.

        Args:
            message: Current user-facing stroke status emitted by the controller.
        """
        self.status.setText(str(message))
        self.finish_button.setEnabled(self.controller.can_finish)

    @staticmethod
    def _modules():
        """Load the installed Qt widget module for the host FreeCAD version.

        Returns:
            FreeCAD application module, GUI module, and Qt widget module.
        """
        if TYPE_CHECKING:
            from PySide2 import QtWidgets
        else:
            try:
                from PySide import QtWidgets
            except ImportError:
                from PySide2 import QtWidgets
        return __import__("FreeCAD"), __import__("FreeCADGui"), QtWidgets

    def finish(self):
        """Finish the selected Surface Pen mode using the task-panel planar tolerance."""
        try:
            result = self.controller.finish(float(self.tolerance.value()))
        except (RuntimeError, ValueError) as exc:
            self.update_status(f"Could not finish Surface Pen: {exc}")
            return False
        open_reference_sketch = (
            str(getattr(result, "SurfaceAuthoring", ""))
            == "ClothPattern.SurfacePen.ReferencePoints"
        )
        self.accept()
        if open_reference_sketch:
            active = self.controller.Gui.activeDocument()
            if active is not None:
                active.setEdit(result.Name)
        return True

    def accept(self):
        """Close the task panel after committing the current surface draft."""
        self.controller.deactivate()
        with contextlib.suppress(AttributeError, RuntimeError):
            self.controller.Gui.Control.closeDialog()
        return True

    def reject(self):
        """Cancel surface drawing and close the task panel without extraction."""
        self.controller.clear()
        self.controller.deactivate()
        with contextlib.suppress(AttributeError, RuntimeError):
            self.controller.Gui.Control.closeDialog()
        return True

    def getStandardButtons(self):
        """Use no standard dialog buttons; actions are explicit in the panel.

        Returns:
            Qt's no-button flag because the panel provides explicit Finish, Clear,
            and Cancel controls.
        """
        if TYPE_CHECKING:
            from PySide2 import QtWidgets
        else:
            try:
                from PySide import QtWidgets
            except ImportError:
                from PySide2 import QtWidgets
        return QtWidgets.QDialogButtonBox.NoButton


def start_surface_pen():
    """Start the public Cloth Pattern 3D Surface Pen command.

    Returns:
        Task panel controlling the newly activated surface pen session.

    Raises:
        RuntimeError: If there is no active document or the selected target is unavailable.
        ValueError: If the document has no selected or discoverable surface target.
    """
    import FreeCAD as App
    import FreeCADGui as Gui

    doc = App.ActiveDocument
    if doc is None:
        msg = "open a garment document before starting the 3D Pattern Pen"
        raise RuntimeError(msg)
    target, source = _surface_target_from_document(doc, Gui)
    if target is None or source is None:
        msg = "select a mannequin/drape target or create one before starting the 3D Pattern Pen"
        raise ValueError(msg)
    controller = SurfacePenController(target, source)
    panel = SurfacePenTaskPanel(controller)
    panel.controller.status_callback = panel.update_status
    controller.activate()
    Gui.Control.showDialog(panel)
    return panel


__all__ = [
    "FlattenedSurfacePatch",
    "SurfaceAnchor",
    "SurfacePenController",
    "SurfacePenTaskPanel",
    "close_surface_stroke",
    "extract_surface_draft_to_pattern",
    "flatten_surface_patch",
    "polygon_area_2d",
    "polygon_self_intersects",
    "simplify_polyline",
    "start_surface_pen",
    "surface_stroke_can_finish",
]
