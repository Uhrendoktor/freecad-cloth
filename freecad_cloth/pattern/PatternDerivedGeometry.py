"""FreeCAD-independent derived geometry and construction marks for patterns."""

from collections.abc import Iterable
from math import atan2, cos, hypot, isfinite

from pydantic.dataclasses import dataclass as pydantic_dataclass
from shapely.geometry import Polygon

from freecad_cloth.pattern.PatternGeometry import (
    LineSegment,
    ParametricPattern,
    Point,
    PolylineSegment,
    QuadraticBezier,
    Segment,
    seam_allowance_outline,
    signed_area,
)


@pydantic_dataclass(frozen=True)
class Notch:
    """Public data model or service class for Notch."""

    id: str
    segment_id: str
    t: float
    depth: float = 3.0

    def validate(self) -> None:
        """Validate this value and raise ValueError when its state is invalid."""
        if not self.id:
            raise ValueError("notch ID must not be empty")
        if not 0.0 <= self.t <= 1.0:
            raise ValueError("notch position must be between 0 and 1")
        if self.depth <= 0:
            raise ValueError("notch depth must be positive")


@pydantic_dataclass(frozen=True)
class PatternMark:
    """A persistent semantic construction mark attached to the sewing line."""

    id: str
    kind: str
    segment_id: str = ""
    t: float = 0.5
    angle: float = 0.0
    length: float = 40.0
    text: str = ""

    def validate(self) -> None:
        """Validate this value and raise ValueError when its state is invalid."""
        if not self.id.strip() or not self.kind.strip():
            raise ValueError("pattern mark ID and kind must not be empty")
        if not 0.0 <= self.t <= 1.0:
            raise ValueError("pattern mark position must be between 0 and 1")
        if self.length <= 0:
            raise ValueError("pattern mark length must be positive")


@pydantic_dataclass(frozen=True)
class OffsetEdge:
    """Public data model or service class for OffsetEdge."""

    id: str
    points: tuple[Point, ...]


@pydantic_dataclass(frozen=True)
class DerivedPattern:
    """Public data model or service class for DerivedPattern."""

    sewing_boundary: ParametricPattern
    cut_boundary: tuple[OffsetEdge, ...]
    notches: tuple[Notch, ...]
    marks: tuple[PatternMark, ...] = ()
    cut_contour: tuple[Point, ...] = ()


def derive_cut_boundary(
    pattern: ParametricPattern,
    width: float,
    edge_widths: dict[str, float] | None = None,
    curve_samples: int = 32,
    miter_limit: float = 4.0,
) -> DerivedPattern:
    """Provide the public derive cut boundary operation."""
    if not isfinite(width) or width < 0:
        raise ValueError("seam allowance width must be finite and non-negative")
    if curve_samples < 2:
        raise ValueError("curve_samples must be at least 2")
    if not isfinite(miter_limit) or miter_limit < 1:
        raise ValueError("miter_limit must be finite and at least 1")
    edge_widths = edge_widths or {}
    unknown = set(edge_widths) - set(pattern.by_id())
    if unknown:
        raise ValueError(f"unknown edge width IDs: {sorted(unknown)}")
    if any(not isfinite(value) or value < 0 for value in edge_widths.values()):
        raise ValueError("seam allowance widths must be finite and non-negative")
    sampled = _sample_segments(pattern.segments, curve_samples)
    outline = [point for points in sampled for point in points[:-1]]
    orientation = signed_area(outline)
    if abs(orientation) < 1e-12 and width:
        raise ValueError("pattern outline must enclose a non-zero area")
    outward_sign = -1.0 if orientation > 0 else 1.0
    cut_edges = []
    effective_widths = []
    for segment, points in zip(pattern.segments, sampled, strict=False):
        allowance = edge_widths.get(segment.id, width)
        effective_widths.append(allowance)
        cut_edges.append(
            OffsetEdge(
                segment.id, tuple(_offset_polyline(points, allowance, outward_sign, miter_limit))
            )
        )

    # A single GEOS polygon buffer gives the common uniform-allowance case a
    # continuous, validated outer perimeter instead of disconnected edge offsets.
    if len(set(effective_widths)) <= 1:
        cut_contour = tuple(
            seam_allowance_outline(
                pattern,
                effective_widths[0],
                curve_samples=curve_samples,
                miter_limit=miter_limit,
            )
        )
    else:
        cut_contour = _join_variable_offset_edges(
            sampled,
            cut_edges,
            effective_widths,
            miter_limit,
        )
        contour_polygon = Polygon(cut_contour)
        if (
            not contour_polygon.is_valid
            or contour_polygon.is_empty
            or contour_polygon.area <= 0.0
            or contour_polygon.interiors
        ):
            raise ValueError("per-edge seam allowance produced an invalid cut contour")
    return DerivedPattern(pattern, tuple(cut_edges), (), (), cut_contour)


def add_notches(derived: DerivedPattern, notches: Iterable[Notch]) -> DerivedPattern:
    """Add the requested notches data."""
    by_id = derived.sewing_boundary.by_id()
    result = list(derived.notches)
    ids = {n.id for n in result} | {m.id for m in derived.marks}
    for notch in notches:
        notch.validate()
        if notch.segment_id not in by_id:
            raise ValueError(f"notch references unknown segment: {notch.segment_id}")
        if notch.id in ids:
            raise ValueError(f"duplicate construction mark ID: {notch.id}")
        ids.add(notch.id)
        result.append(notch)
    return DerivedPattern(
        derived.sewing_boundary,
        derived.cut_boundary,
        tuple(result),
        derived.marks,
        derived.cut_contour,
    )


def add_marks(derived: DerivedPattern, marks: Iterable[PatternMark]) -> DerivedPattern:
    """Add the requested marks data."""
    by_id = derived.sewing_boundary.by_id()
    result = list(derived.marks)
    ids = {n.id for n in derived.notches} | {m.id for m in result}
    for mark in marks:
        mark.validate()
        if mark.segment_id and mark.segment_id not in by_id:
            raise ValueError(f"pattern mark references unknown segment: {mark.segment_id}")
        if mark.id in ids:
            raise ValueError(f"duplicate construction mark ID: {mark.id}")
        ids.add(mark.id)
        result.append(mark)
    return DerivedPattern(
        derived.sewing_boundary,
        derived.cut_boundary,
        derived.notches,
        tuple(result),
        derived.cut_contour,
    )


def notch_point(pattern: ParametricPattern, notch: Notch) -> Point:
    """Provide the public notch point operation."""
    notch.validate()
    segment = pattern.by_id().get(notch.segment_id)
    if segment is None:
        raise ValueError(f"notch references unknown segment: {notch.segment_id}")
    return segment.point(notch.t)


def mark_point(pattern: ParametricPattern, mark: PatternMark) -> Point:
    """Provide the public mark point operation."""
    mark.validate()
    if not mark.segment_id:
        return pattern.sampled_outline(2)[0]
    segment = pattern.by_id().get(mark.segment_id)
    if segment is None:
        raise ValueError(f"pattern mark references unknown segment: {mark.segment_id}")
    return segment.point(mark.t)


def _sample_segments(segments: Iterable[Segment], curve_samples: int) -> list[list[Point]]:
    result = []
    for segment in segments:
        if isinstance(segment, LineSegment):
            result.append([segment.start, segment.end])
        elif isinstance(segment, (QuadraticBezier, PolylineSegment)):
            result.append(segment.polyline(curve_samples))
        else:
            raise TypeError(f"unsupported segment type: {type(segment).__name__}")
    return result


def _join_variable_offset_edges(
    sampled: list[list[Point]],
    cut_edges: list[OffsetEdge],
    allowances: list[float],
    miter_limit: float,
) -> tuple[Point, ...]:
    """Join varying per-edge offsets with mitres or bevel connectors."""
    count = len(cut_edges)
    joints: list[tuple[Point, Point]] = []
    for index in range(count):
        previous_index = (index - 1) % count
        previous = cut_edges[previous_index].points
        current = cut_edges[index].points
        current_source = sampled[index]
        previous_end = previous[-1]
        current_start = current[0]
        corner = current_source[0]
        a = previous[-2]
        b = previous[-1]
        c = current[0]
        d = current[1]
        intersection = _line_intersection(a, b, c, d)
        allowance = max(allowances[previous_index], allowances[index])
        if (
            intersection is not None
            and hypot(intersection[0] - corner[0], intersection[1] - corner[1])
            <= max(allowance, 1e-9) * miter_limit
        ):
            joints.append((intersection, intersection))
        elif (
            hypot(
                previous_end[0] - current_start[0],
                previous_end[1] - current_start[1],
            )
            <= 1e-9
        ):
            midpoint = (
                (previous_end[0] + current_start[0]) / 2.0,
                (previous_end[1] + current_start[1]) / 2.0,
            )
            joints.append((midpoint, midpoint))
        else:
            # Keeping both offset endpoints creates an explicit bevel segment
            # when the joined contour is assembled below.
            joints.append((previous_end, current_start))

    contour: list[Point] = []
    for index, edge in enumerate(cut_edges):
        points = list(edge.points)
        points[0] = joints[index][1]
        points[-1] = joints[(index + 1) % count][0]
        for point in points:
            if not contour or hypot(point[0] - contour[-1][0], point[1] - contour[-1][1]) > 1e-9:
                contour.append(point)

    if (
        len(contour) > 1
        and hypot(contour[-1][0] - contour[0][0], contour[-1][1] - contour[0][1]) <= 1e-9
    ):
        contour.pop()
    if len(contour) < 3:
        raise ValueError("per-edge seam allowance produced fewer than three cut points")
    return tuple(contour)


def _line_intersection(a: Point, b: Point, c: Point, d: Point) -> Point | None:
    """Intersect two infinite 2D lines, returning None for parallel lines."""
    ax, ay = b[0] - a[0], b[1] - a[1]
    bx, by = d[0] - c[0], d[1] - c[1]
    denominator = ax * by - ay * bx
    if abs(denominator) < 1e-12:
        return None
    fraction = ((c[0] - a[0]) * by - (c[1] - a[1]) * bx) / denominator
    return (a[0] + fraction * ax, a[1] + fraction * ay)


def _offset_polyline(
    points: list[Point], width: float, outward_sign: float, miter_limit: float
) -> list[Point]:
    if width == 0:
        return list(points)
    if len(points) < 2:
        raise ValueError("an edge needs at least two points")
    normals = []
    for a, b in zip(points, points[1:], strict=False):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = hypot(dx, dy)
        normals.append(
            (0.0, 0.0)
            if length == 0
            else (outward_sign * (-dy / length), outward_sign * (dx / length))
        )
    result = []
    for index, point in enumerate(points):
        if index == 0:
            normal = normals[0]
        elif index == len(points) - 1:
            normal = normals[-1]
        else:
            n1, n2 = normals[index - 1], normals[index]
            summed = (n1[0] + n2[0], n1[1] + n2[1])
            norm = hypot(*summed)
            normal = n2 if norm == 0 else (summed[0] / norm, summed[1] / norm)
        scale = width
        if index not in (0, len(points) - 1):
            tangent_change = abs(
                atan2(normals[index][1], normals[index][0])
                - atan2(normals[index - 1][1], normals[index - 1][0])
            )
            while tangent_change > 3.141592653589793:
                tangent_change -= 2 * 3.141592653589793
            cosine_half = max(0.25, abs(cos(tangent_change / 2)))
            scale = min(width / cosine_half, width * miter_limit)
        result.append((point[0] + normal[0] * scale, point[1] + normal[1] * scale))
    return result
