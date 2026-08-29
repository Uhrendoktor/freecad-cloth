"""FreeCAD-independent sewing edge geometry and stitch correspondence helpers.

PatternModel.Seam stores semantic references; this module turns those references
into deterministic geometric samples without coupling the model to FreeCAD or
the simulation solver.  Edges may be straight outline segments or an optional
sampled curve supplied by a document adapter.
"""
from math import hypot
from typing import Iterable, Sequence, Tuple

Point2 = Tuple[float, float]


def polyline_length(points: Sequence[Point2]) -> float:
    if len(points) < 2:
        raise ValueError("an edge needs at least two points")
    return sum(hypot(points[i + 1][0] - points[i][0], points[i + 1][1] - points[i][1]) for i in range(len(points) - 1))


def sample_polyline(points: Sequence[Point2], start: float, end: float, count: int) -> Tuple[Point2, ...]:
    """Sample a polyline by normalized arc length, including both endpoints."""
    if len(points) < 2:
        raise ValueError("an edge needs at least two points")
    start, end = float(start), float(end)
    count = int(count)
    if not 0.0 <= start < end <= 1.0:
        raise ValueError("normalized edge range must satisfy 0 <= start < end <= 1")
    if count < 2:
        raise ValueError("an edge sample needs at least two points")
    lengths = [0.0]
    for i in range(len(points) - 1):
        lengths.append(lengths[-1] + hypot(points[i + 1][0] - points[i][0], points[i + 1][1] - points[i][1]))
    total = lengths[-1]
    if total <= 1e-12:
        raise ValueError("edge has zero length")

    result = []
    for i in range(count):
        target = (start + (end - start) * i / float(count - 1)) * total
        segment = 1
        while segment < len(lengths) - 1 and lengths[segment] < target:
            segment += 1
        lo, hi = lengths[segment - 1], lengths[segment]
        alpha = 0.0 if hi <= lo else (target - lo) / (hi - lo)
        a, b = points[segment - 1], points[segment]
        result.append((a[0] + (b[0] - a[0]) * alpha, a[1] + (b[1] - a[1]) * alpha))
    return tuple(result)


def correspondence(edge_a: Sequence[Point2], edge_b: Sequence[Point2], start_a: float, end_a: float,
                    start_b: float, end_b: float, count: int = 8, reversed_b: bool = False):
    """Return equal-cardinality samples for a semantic seam pair.

    Correspondence is normalized along each seam range, so unequal physical
    lengths are preserved and reported by callers rather than silently scaled.
    Reversal is applied exactly once to B after sampling.
    """
    a = list(sample_polyline(edge_a, start_a, end_a, max(2, int(count))))
    b = list(sample_polyline(edge_b, start_b, end_b, max(2, int(count))))
    if reversed_b:
        b.reverse()
    return tuple(zip(a, b))


def outline_edge(outline: Sequence[Point2], edge: int) -> Tuple[Point2, Point2]:
    if edge < 0 or edge >= len(outline):
        raise ValueError(f"seam edge {edge} is outside the pattern boundary")
    return outline[edge], outline[(edge + 1) % len(outline)]
