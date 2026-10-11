"""FreeCAD-independent parametric 2D pattern geometry primitives."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from math import hypot, isfinite

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


@dataclass(frozen=True)
class LineSegment:
    """Public data model or service class for LineSegment."""

    id: str
    start: Point
    end: Point

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("segment ID must be a non-empty string")
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


@dataclass(frozen=True)
class QuadraticBezier:
    """Public data model or service class for QuadraticBezier."""

    id: str
    start: Point
    control: Point
    end: Point

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("segment ID must be a non-empty string")
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


@dataclass(frozen=True)
class PolylineSegment:
    """A deterministic sampled native curve segment used for derived export."""

    id: str
    points: tuple[Point, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("segment ID must be a non-empty string")
        points = validate_points2d(self.points)
        if len(points) < 2:
            raise ValueError("polyline segment needs at least two points")
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
                raise ValueError("polyline length must be finite")
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
        total = sum(_distance(a, b) for a, b in zip(self.points, self.points[1:], strict=False))
        if not isfinite(total):
            raise ValueError("polyline length must be finite")
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
            raise TypeError("pattern segments must be supported segment types")
        # Recheck coordinates in case a caller bypassed frozen dataclasses.
        for segment in self.segments:
            if isinstance(segment, LineSegment):
                validate_points2d((segment.start, segment.end))
            elif isinstance(segment, QuadraticBezier):
                validate_points2d((segment.start, segment.control, segment.end))
            else:
                validate_points2d(segment.points)
        if len(self.segments) < 3:
            raise ValueError("pattern needs at least three boundary segments")
        ids = [segment.id for segment in self.segments]
        if len(set(ids)) != len(ids):
            raise ValueError("boundary segment IDs must be unique")
        for index, segment in enumerate(self.segments):
            following = self.segments[(index + 1) % len(self.segments)]
            if _distance(segment.end, following.start) > 1e-7:
                raise ValueError(f"boundary is not closed between {segment.id} and {following.id}")

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
                values[segment.id] = sum(
                    _distance(a, b) for a, b in zip(points, points[1:], strict=False)
                )
            if not isfinite(values[segment.id]):
                raise ValueError("pattern segment lengths must be finite")
        return values


def seam_allowance_outline(
    pattern: ParametricPattern, allowance: float, curve_samples: int = 32
) -> list[Point]:
    """Return a valid cut-line offset using GEOS polygon buffering.

    The sewing boundary remains authoritative. GEOS resolves concave offset
    topology (including narrow notches) rather than joining infinite offset
    lines into a potentially self-intersecting ring.
    """
    options = SeamAllowanceOptions(allowance=allowance, curve_samples=curve_samples)
    allowance, curve_samples = options.allowance, options.curve_samples
    points = pattern.sampled_outline(curve_samples)
    if len(points) < 3:
        raise ValueError("pattern needs at least three outline points")
    area = signed_area(points)
    if abs(area) < 1e-12:
        raise ValueError("pattern outline must enclose a non-zero area")
    if allowance == 0.0:
        return list(points)

    source = Polygon(points)
    if source.is_empty or not source.is_valid or source.area <= 0.0:
        raise ValueError("pattern outline must be a valid simple polygon")
    try:
        offset = source.buffer(allowance, join_style="mitre", mitre_limit=5.0)
    except GEOSException as exc:
        raise ValueError("seam allowance offset failed") from exc
    if offset.is_empty or not offset.is_valid or offset.geom_type != "Polygon" or offset.interiors:
        raise ValueError("seam allowance produced invalid or unsupported polygon topology")

    outline = list(
        validate_points2d([(float(x), float(y)) for x, y in offset.exterior.coords[:-1]])
    )
    if len(outline) < 3:
        raise ValueError("seam allowance produced fewer than three boundary points")

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
        raise ValueError("pattern outline area must be finite")
    return area


def _line_intersection(a1: Point, a2: Point, b1: Point, b2: Point) -> Point | None:
    ax, ay = a2[0] - a1[0], a2[1] - a1[1]
    bx, by = b2[0] - b1[0], b2[1] - b1[1]
    denominator = ax * by - ay * bx
    if not isfinite(denominator):
        raise ValueError("offset line intersection must be finite")
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
        raise ValueError("computed geometry point must be finite")
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
        raise ValueError("computed segment length must be finite")
    return distance
