# Copyright (C) 2026 FreeCAD Cloth contributors
"""FreeCAD-independent parametric 2D pattern geometry primitives."""

from collections.abc import Iterable, Sequence
from itertools import starmap
from math import hypot, isfinite

from pydantic.dataclasses import dataclass as pydantic_dataclass
from shapely.errors import GEOSException
from shapely.geometry import Polygon

from freecad_cloth.common.ValidationModels import (
    RectangleDimensions,
    SampleCount,
    SeamAllowanceOptions,
    validate_finite_number,
    validate_point2d,
    validate_points2d,
)

Point = tuple[float, float]


@pydantic_dataclass(frozen=True)
class LineSegment:
    """Public data model or service class for LineSegment."""

    id: str
    start: Point
    end: Point

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            msg = "segment ID must be a non-empty string"
            raise ValueError(msg)
        object.__setattr__(self, "start", validate_point2d(self.start))
        object.__setattr__(self, "end", validate_point2d(self.end))

    def point(self, t: float) -> Point:
        """Return the point at the requested parameter."""
        t = validate_finite_number(t)
        return _require_finite_point(
            (_lerp(self.start[0], self.end[0], t), _lerp(self.start[1], self.end[1], t))
        )

    def length(self) -> float:
        """Return the finite geometric length represented by this object."""
        return _distance(self.start, self.end)


@pydantic_dataclass(frozen=True)
class QuadraticBezier:
    """Public data model or service class for QuadraticBezier."""

    id: str
    start: Point
    control: Point
    end: Point

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            msg = "segment ID must be a non-empty string"
            raise ValueError(msg)
        object.__setattr__(self, "start", validate_point2d(self.start))
        object.__setattr__(self, "control", validate_point2d(self.control))
        object.__setattr__(self, "end", validate_point2d(self.end))

    def point(self, t: float) -> Point:
        """Return the point at the requested parameter."""
        t = validate_finite_number(t)
        first = (
            _lerp(self.start[0], self.control[0], t),
            _lerp(self.start[1], self.control[1], t),
        )
        second = (
            _lerp(self.control[0], self.end[0], t),
            _lerp(self.control[1], self.end[1], t),
        )
        return _require_finite_point((_lerp(first[0], second[0], t), _lerp(first[1], second[1], t)))

    def polyline(self, samples: int = 32) -> list[Point]:
        """Return sampled polyline points for this geometry."""
        samples = SampleCount(count=samples).count
        return [self.point(i / (samples - 1)) for i in range(samples)]


@pydantic_dataclass(frozen=True)
class PolylineSegment:
    """A deterministic sampled native curve segment used for derived export."""

    id: str
    points: tuple[Point, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            msg = "segment ID must be a non-empty string"
            raise ValueError(msg)
        points = validate_points2d(self.points)
        if len(points) < 2:
            msg = "polyline segment needs at least two points"
            raise ValueError(msg)
        object.__setattr__(self, "points", points)

    @property
    def start(self) -> Point:
        """Provide the public start operation."""
        return self.points[0]

    @property
    def end(self) -> Point:
        """End the synchronized editing session."""
        return self.points[-1]

    def point(self, t: float) -> Point:
        """Return the point at the requested parameter."""
        fraction = min(1.0, max(0.0, validate_finite_number(t)))
        lengths = [0.0]
        for a, b in zip(self.points, self.points[1:], strict=False):
            total_length = lengths[-1] + _distance(a, b)
            if not isfinite(total_length):
                msg = "polyline length must be finite"
                raise ValueError(msg)
            lengths.append(total_length)
        total = lengths[-1]
        if total <= 1e-12:
            return self.points[0]
        target = fraction * total
        for index in range(1, len(self.points)):
            if target <= lengths[index]:
                span = lengths[index] - lengths[index - 1]
                local = 0.0 if span <= 1e-12 else (target - lengths[index - 1]) / span
                a, b = self.points[index - 1], self.points[index]
                return _require_finite_point((_lerp(a[0], b[0], local), _lerp(a[1], b[1], local)))
        return self.points[-1]

    def polyline(self, samples: int = 32) -> list[Point]:
        """Return sampled polyline points for this geometry."""
        return list(self.points)

    def length(self) -> float:
        """Return the geometric length represented by this object."""
        total = sum(starmap(_distance, zip(self.points, self.points[1:], strict=False)))
        if not isfinite(total):
            msg = "polyline length must be finite"
            raise ValueError(msg)
        return total


Segment = LineSegment | QuadraticBezier | PolylineSegment


class ParametricPattern:
    """Ordered closed boundary generated from explicit parameters.

    Segment IDs are supplied by the caller and are therefore stable across
    regeneration as long as the topology is unchanged.
    """

    def __init__(self, segments: Iterable[Segment]) -> None:
        self.segments = list(segments)
        self.validate()

    def validate(self) -> None:
        """Validate this value and raise ValueError when its state is invalid."""
        if any(
            not isinstance(segment, (LineSegment, QuadraticBezier, PolylineSegment))
            for segment in self.segments
        ):
            msg = "pattern segments must be supported segment types"
            raise TypeError(msg)
        # Recheck coordinates in case a caller bypassed frozen dataclasses.
        for segment in self.segments:
            if isinstance(segment, LineSegment):
                validate_points2d((segment.start, segment.end))
            elif isinstance(segment, QuadraticBezier):
                validate_points2d((segment.start, segment.control, segment.end))
            else:
                validate_points2d(segment.points)
        if len(self.segments) < 3:
            msg = "pattern needs at least three boundary segments"
            raise ValueError(msg)
        ids = [segment.id for segment in self.segments]
        if len(set(ids)) != len(ids):
            msg = "boundary segment IDs must be unique"
            raise ValueError(msg)
        for index, segment in enumerate(self.segments):
            following = self.segments[(index + 1) % len(self.segments)]
            if _distance(segment.end, following.start) > 1e-7:
                msg = f"boundary is not closed between {segment.id} and {following.id}"
                raise ValueError(msg)

    def by_id(self) -> dict[str, Segment]:
        """Provide the public by id operation."""
        return {segment.id: segment for segment in self.segments}

    def sampled_outline(self, curve_samples: int = 32) -> list[Point]:
        """Provide the public sampled outline operation."""
        curve_samples = SampleCount(count=curve_samples).count
        result: list[Point] = []
        for segment in self.segments:
            if isinstance(segment, LineSegment):
                result.append(segment.start)
            else:
                result.extend(segment.polyline(curve_samples)[:-1])
        return result

    def lengths(self, curve_samples: int = 128) -> dict[str, float]:
        """Provide the public lengths operation."""
        curve_samples = SampleCount(count=curve_samples).count
        values: dict[str, float] = {}
        for segment in self.segments:
            if isinstance(segment, LineSegment):
                values[segment.id] = segment.length()
            else:
                points = segment.polyline(curve_samples)
                values[segment.id] = sum(starmap(_distance, zip(points, points[1:], strict=False)))
            if not isfinite(values[segment.id]):
                msg = "pattern segment lengths must be finite"
                raise ValueError(msg)
        return values


def seam_allowance_outline(
    pattern: ParametricPattern,
    allowance: float,
    curve_samples: int = 32,
    miter_limit: float = 5.0,
) -> list[Point]:
    """Return a valid cut-line offset using GEOS polygon buffering.

    The sewing boundary remains authoritative. GEOS resolves concave offset
    topology (including narrow notches) rather than joining infinite offset
    lines into a potentially self-intersecting ring.
    """
    options = SeamAllowanceOptions(allowance=allowance, curve_samples=curve_samples)
    allowance, curve_samples = options.allowance, options.curve_samples
    if not isfinite(miter_limit) or miter_limit < 1.0:
        msg = "miter limit must be finite and at least 1"
        raise ValueError(msg)
    points = pattern.sampled_outline(curve_samples)
    if len(points) < 3:
        msg = "pattern needs at least three outline points"
        raise ValueError(msg)
    area = signed_area(points)
    if abs(area) < 1e-12:
        msg = "pattern outline must enclose a non-zero area"
        raise ValueError(msg)
    if allowance == 0.0:
        return list(points)

    source = Polygon(points)
    if source.is_empty or not source.is_valid or source.area <= 0.0:
        msg = "pattern outline must be a valid simple polygon"
        raise ValueError(msg)
    try:
        offset = source.buffer(allowance, join_style="mitre", mitre_limit=miter_limit)
    except GEOSException as exc:
        msg = "seam allowance offset failed"
        raise ValueError(msg) from exc
    if offset.is_empty or not offset.is_valid or offset.geom_type != "Polygon" or offset.interiors:
        msg = "seam allowance produced invalid or unsupported polygon topology"
        raise ValueError(msg)

    outline = list(
        validate_points2d([(float(x), float(y)) for x, y in offset.exterior.coords[:-1]])
    )
    if len(outline) < 3:
        msg = "seam allowance produced fewer than three boundary points"
        raise ValueError(msg)

    # Keep deterministic edge ordering and the input winding for legacy callers.
    start_index = min(
        range(len(outline)),
        key=lambda index: (
            hypot(outline[index][0] - points[0][0], outline[index][1] - points[0][1]),
            index,
        ),
    )
    outline = outline[start_index:] + outline[:start_index]
    if (signed_area(outline) > 0.0) != (area > 0.0):
        outline = [outline[0], *reversed(outline[1:])]
    return outline


def signed_area(points: Sequence[Point]) -> float:
    """Return the signed shoelace area of a closed 2D polygon."""
    area = 0.5 * sum(
        points[i][0] * points[(i + 1) % len(points)][1]
        - points[(i + 1) % len(points)][0] * points[i][1]
        for i in range(len(points))
    )
    if not isfinite(area):
        msg = "pattern outline area must be finite"
        raise ValueError(msg)
    return area


def _line_intersection(a1: Point, a2: Point, b1: Point, b2: Point) -> Point | None:
    ax, ay = a2[0] - a1[0], a2[1] - a1[1]
    bx, by = b2[0] - b1[0], b2[1] - b1[1]
    denominator = ax * by - ay * bx
    if not isfinite(denominator):
        msg = "offset line intersection must be finite"
        raise ValueError(msg)
    if abs(denominator) < 1e-12:
        return None
    cx, cy = b1[0] - a1[0], b1[1] - a1[1]
    t = (cx * by - cy * bx) / denominator
    return _require_finite_point((a1[0] + t * ax, a1[1] + t * ay))


def _lerp(start: float, end: float, fraction: float) -> float:
    """Interpolate robustly on [0, 1] and preserve extrapolation elsewhere."""
    if 0.0 <= fraction <= 1.0:
        return start * (1.0 - fraction) + end * fraction
    return start + (end - start) * fraction


def _require_finite_point(point: Point) -> Point:
    """Reject non-finite values produced by otherwise finite arithmetic."""
    if not all(isfinite(value) for value in point):
        msg = "computed geometry point must be finite"
        raise ValueError(msg)
    return point


def rectangle(width: float, height: float) -> ParametricPattern:
    """Create a deterministic rectangular pattern from dimensions in mm."""
    dimensions = RectangleDimensions(width=width, height=height)
    width, height = dimensions.width, dimensions.height
    return ParametricPattern(
        [
            LineSegment("bottom", (0.0, 0.0), (width, 0.0)),
            LineSegment("right", (width, 0.0), (width, height)),
            LineSegment("top", (width, height), (0.0, height)),
            LineSegment("left", (0.0, height), (0.0, 0.0)),
        ]
    )


def _distance(a: Point, b: Point) -> float:
    distance = hypot(a[0] - b[0], a[1] - b[1])
    if not isfinite(distance):
        msg = "computed segment length must be finite"
        raise ValueError(msg)
    return distance
