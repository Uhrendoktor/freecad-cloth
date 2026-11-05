# Copyright (C) 2026 FreeCAD Cloth contributors
"""FreeCAD-independent derived geometry and construction marks for patterns."""

from collections.abc import Iterable
from math import hypot, isfinite

from pydantic import ConfigDict
from pydantic.dataclasses import dataclass as pydantic_dataclass
from shapely.geometry import LineString, Polygon

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
        """Validate notch identity, position and positive depth.

        Raises:
            ValueError: If the identity is empty, the normalized position is outside
                the unit interval, or the depth is not positive.
        """
        if not self.id:
            msg = "notch ID must not be empty"
            raise ValueError(msg)
        if not 0.0 <= self.t <= 1.0:
            msg = "notch position must be between 0 and 1"
            raise ValueError(msg)
        if self.depth <= 0:
            msg = "notch depth must be positive"
            raise ValueError(msg)


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
        """Validate mark identity, kind, position and positive length.

        Raises:
            ValueError: If the identity or kind is empty, the normalized position
                is outside the unit interval, or the mark length is not positive.
        """
        if not self.id.strip() or not self.kind.strip():
            msg = "pattern mark ID and kind must not be empty"
            raise ValueError(msg)
        if not 0.0 <= self.t <= 1.0:
            msg = "pattern mark position must be between 0 and 1"
            raise ValueError(msg)
        if self.length <= 0:
            msg = "pattern mark length must be positive"
            raise ValueError(msg)


@pydantic_dataclass(frozen=True)
class OffsetEdge:
    """One derived cut-boundary edge with its stable identity and sampled points."""

    id: str
    points: tuple[Point, ...]


@pydantic_dataclass(frozen=True, config=ConfigDict(arbitrary_types_allowed=True))
class DerivedPattern:
    """Immutable sewing boundary, per-edge cut offsets, marks and closed contour."""

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
    """Derive seam-allowance offsets and validate the resulting cut contour.

    Args:
        pattern: Authored parametric sewing boundary whose segments define the piece.
        width: Default outward allowance in millimetres for edges without overrides.
        edge_widths: Optional mapping of segment IDs to per-edge allowance widths.
        curve_samples: Number of samples used when approximating curved segments.
        miter_limit: Maximum corner-miter extension as a multiple of allowance width.

    Returns:
        Derived geometry containing the source boundary, offset edge polylines and
        a joined outer cut contour.

    Raises:
        ValueError: If an allowance or sampling option is invalid, an edge ID is
            unknown, or the derived contour is invalid or self-intersecting.
        TypeError: If the source boundary contains an unsupported segment type.
    """
    if not isfinite(width) or width < 0:
        msg = "seam allowance width must be finite and non-negative"
        raise ValueError(msg)
    if curve_samples < 2:
        msg = "curve_samples must be at least 2"
        raise ValueError(msg)
    if not isfinite(miter_limit) or miter_limit < 1:
        msg = "miter_limit must be finite and at least 1"
        raise ValueError(msg)
    edge_widths = edge_widths or {}
    unknown = set(edge_widths) - set(pattern.by_id())
    if unknown:
        msg = f"unknown edge width IDs: {sorted(unknown)}"
        raise ValueError(msg)
    if any(not isfinite(value) or value < 0 for value in edge_widths.values()):
        msg = "seam allowance widths must be finite and non-negative"
        raise ValueError(msg)
    sampled = _sample_segments(pattern.segments, curve_samples)
    outline = [point for points in sampled for point in points[:-1]]
    orientation = signed_area(outline)
    if abs(orientation) < 1e-12 and width:
        msg = "pattern outline must enclose a non-zero area"
        raise ValueError(msg)
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
            msg = "per-edge seam allowance produced an invalid cut contour"
            raise ValueError(msg)
    return DerivedPattern(pattern, tuple(cut_edges), (), (), cut_contour)


def add_notches(derived: DerivedPattern, notches: Iterable[Notch]) -> DerivedPattern:
    """Return a derived pattern with the requested notches appended.

    Args:
        derived: Existing immutable result containing the authoritative sewing boundary.
        notches: Notch records to validate and attach to their referenced segments.

    Returns:
        A new derived pattern that retains existing geometry and includes the notches.

    Raises:
        ValueError: If a notch is invalid, references an unknown segment, or reuses
            an existing notch or construction-mark ID.
    """
    by_id = derived.sewing_boundary.by_id()
    result = list(derived.notches)
    ids = {n.id for n in result} | {m.id for m in derived.marks}
    for notch in notches:
        notch.validate()
        if notch.segment_id not in by_id:
            msg = f"notch references unknown segment: {notch.segment_id}"
            raise ValueError(msg)
        if notch.id in ids:
            msg = f"duplicate construction mark ID: {notch.id}"
            raise ValueError(msg)
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
    """Return a derived pattern with the requested construction marks appended.

    Args:
        derived: Existing immutable result containing the authoritative sewing boundary.
        marks: Construction marks to validate and attach to their referenced segments.

    Returns:
        A new derived pattern that retains existing geometry and includes the marks.

    Raises:
        ValueError: If a mark is invalid, references an unknown segment, or reuses
            an existing notch or construction-mark ID.
    """
    by_id = derived.sewing_boundary.by_id()
    result = list(derived.marks)
    ids = {n.id for n in derived.notches} | {m.id for m in result}
    for mark in marks:
        mark.validate()
        if mark.segment_id and mark.segment_id not in by_id:
            msg = f"pattern mark references unknown segment: {mark.segment_id}"
            raise ValueError(msg)
        if mark.id in ids:
            msg = f"duplicate construction mark ID: {mark.id}"
            raise ValueError(msg)
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
    """Resolve the boundary coordinate at a validated notch position.

    Args:
        pattern: Authored parametric boundary containing the referenced segment.
        notch: Notch identity, segment reference, normalized position and depth.

    Returns:
        The 2D point where the notch intersects its sewing segment.

    Raises:
        ValueError: If the notch is invalid or references a missing segment.
    """
    notch.validate()
    segment = pattern.by_id().get(notch.segment_id)
    if segment is None:
        msg = f"notch references unknown segment: {notch.segment_id}"
        raise ValueError(msg)
    return segment.point(notch.t)


def mark_point(pattern: ParametricPattern, mark: PatternMark) -> Point:
    """Resolve the boundary coordinate associated with a construction mark.

    Args:
        pattern: Authored parametric boundary containing the referenced segment.
        mark: Construction mark to locate; an empty segment ID denotes the first
            point of the sampled outline.

    Returns:
        The 2D point associated with the mark.

    Raises:
        ValueError: If the mark is invalid or references a missing segment.
    """
    mark.validate()
    if not mark.segment_id:
        return pattern.sampled_outline(2)[0]
    segment = pattern.by_id().get(mark.segment_id)
    if segment is None:
        msg = f"pattern mark references unknown segment: {mark.segment_id}"
        raise ValueError(msg)
    return segment.point(mark.t)


def _sample_segments(segments: Iterable[Segment], curve_samples: int) -> list[list[Point]]:
    """Sample each segment into an ordered point list for offset construction.

    Args:
        segments: Ordered line, Bezier or polyline segments of the source boundary.
        curve_samples: Sampling density passed to curved-segment approximations.

    Returns:
        One ordered point list per source segment, with endpoints retained.

    Raises:
        TypeError: If a segment implementation is not supported by the offsetter.
    """
    result = []
    for segment in segments:
        if isinstance(segment, LineSegment):
            result.append([segment.start, segment.end])
        elif isinstance(segment, (QuadraticBezier, PolylineSegment)):
            result.append(segment.polyline(curve_samples))
        else:
            msg = f"unsupported segment type: {type(segment).__name__}"
            raise TypeError(msg)
    return result


def _join_variable_offset_edges(
    sampled: list[list[Point]],
    cut_edges: list[OffsetEdge],
    allowances: list[float],
    miter_limit: float,
) -> tuple[Point, ...]:
    """Join neighboring offset edges using bounded mitres or bevel connectors.

    Args:
        sampled: Source polyline samples used to locate each original corner.
        cut_edges: Per-edge offset polylines in source-boundary order.
        allowances: Effective allowance width for each corresponding source edge.
        miter_limit: Maximum miter extension relative to the larger adjacent width.

    Returns:
        A closed contour assembled from offset edges and their corner connectors.

    Raises:
        ValueError: If fewer than three distinct cut-contour points remain.
    """
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
        msg = "per-edge seam allowance produced fewer than three cut points"
        raise ValueError(msg)
    return tuple(contour)


def _line_intersection(a: Point, b: Point, c: Point, d: Point) -> Point | None:
    """Intersect two infinite 2D lines unless their direction vectors are parallel.

    Args:
        a: Start point of the first line.
        b: End point of the first line.
        c: Start point of the second line.
        d: End point of the second line.

    Returns:
        Intersection point, or None when the lines are parallel.
    """
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
    """Offset a sampled edge using GEOS rather than Python-level vertex loops.

    Args:
        points: Ordered 2D coordinates of the source edge.
        width: Offset distance in pattern millimetres.
        outward_sign: 1 for left-side offsets and -1 for right-side offsets.
        miter_limit: Maximum miter extension relative to the requested distance.

    Returns:
        Offset coordinates ordered in the same endpoint direction as the source.

    Raises:
        ValueError: If the edge is too short or GEOS cannot return one offset line.
    """
    if width == 0:
        return list(points)
    if len(points) < 2:
        msg = "an edge needs at least two points"
        raise ValueError(msg)
    offset = LineString(points).offset_curve(
        width * outward_sign,
        join_style="mitre",
        mitre_limit=miter_limit,
    )
    if offset.is_empty or offset.geom_type != "LineString" or len(offset.coords) < 2:
        msg = "GEOS could not produce one continuous offset polyline"
        raise ValueError(msg)
    result = [(float(x), float(y)) for x, y in offset.coords]
    start = points[0]
    first_distance = hypot(result[0][0] - start[0], result[0][1] - start[1])
    last_distance = hypot(result[-1][0] - start[0], result[-1][1] - start[1])
    if last_distance < first_distance:
        result.reverse()
    return result
