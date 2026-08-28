"""FreeCAD-independent parametric 2D pattern geometry primitives."""
from dataclasses import dataclass
from math import hypot
from typing import Dict, Iterable, List, Tuple

Point = Tuple[float, float]


@dataclass(frozen=True)
class LineSegment:
    id: str
    start: Point
    end: Point

    def point(self, t: float) -> Point:
        return (
            self.start[0] + (self.end[0] - self.start[0]) * t,
            self.start[1] + (self.end[1] - self.start[1]) * t,
        )

    def length(self) -> float:
        return hypot(self.end[0] - self.start[0], self.end[1] - self.start[1])


@dataclass(frozen=True)
class QuadraticBezier:
    id: str
    start: Point
    control: Point
    end: Point

    def point(self, t: float) -> Point:
        u = 1.0 - t
        return (
            u * u * self.start[0] + 2 * u * t * self.control[0] + t * t * self.end[0],
            u * u * self.start[1] + 2 * u * t * self.control[1] + t * t * self.end[1],
        )

    def polyline(self, samples: int = 32) -> List[Point]:
        if samples < 2:
            raise ValueError("samples must be at least 2")
        return [self.point(i / (samples - 1)) for i in range(samples)]


Segment = LineSegment | QuadraticBezier


class ParametricPattern:
    """Ordered closed boundary generated from explicit parameters.

    Segment IDs are supplied by the caller and are therefore stable across
    regeneration as long as the topology is unchanged.
    """

    def __init__(self, segments: Iterable[Segment]):
        self.segments = list(segments)
        self.validate()

    def validate(self) -> None:
        if len(self.segments) < 3:
            raise ValueError("pattern needs at least three boundary segments")
        ids = [segment.id for segment in self.segments]
        if len(set(ids)) != len(ids):
            raise ValueError("boundary segment IDs must be unique")
        for index, segment in enumerate(self.segments):
            following = self.segments[(index + 1) % len(self.segments)]
            if _distance(segment.end, following.start) > 1e-7:
                raise ValueError(f"boundary is not closed between {segment.id} and {following.id}")

    def by_id(self) -> Dict[str, Segment]:
        return {segment.id: segment for segment in self.segments}

    def sampled_outline(self, curve_samples: int = 32) -> List[Point]:
        result: List[Point] = []
        for segment in self.segments:
            if isinstance(segment, LineSegment):
                result.append(segment.start)
            else:
                result.extend(segment.polyline(curve_samples)[:-1])
        return result

    def lengths(self, curve_samples: int = 128) -> Dict[str, float]:
        values: Dict[str, float] = {}
        for segment in self.segments:
            if isinstance(segment, LineSegment):
                values[segment.id] = segment.length()
            else:
                points = segment.polyline(curve_samples)
                values[segment.id] = sum(_distance(a, b) for a, b in zip(points, points[1:]))
        return values


def rectangle(width: float, height: float) -> ParametricPattern:
    """Create a deterministic rectangular pattern from dimensions in mm."""
    if width <= 0 or height <= 0:
        raise ValueError("rectangle dimensions must be positive")
    return ParametricPattern([
        LineSegment("bottom", (0.0, 0.0), (width, 0.0)),
        LineSegment("right", (width, 0.0), (width, height)),
        LineSegment("top", (width, height), (0.0, height)),
        LineSegment("left", (0.0, height), (0.0, 0.0)),
    ])


def _distance(a: Point, b: Point) -> float:
    return hypot(a[0] - b[0], a[1] - b[1])
