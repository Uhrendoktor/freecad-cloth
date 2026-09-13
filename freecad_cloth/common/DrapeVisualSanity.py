"""Solver-neutral visual sanity metrics for generated garment drapes."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt
from typing import Sequence, Tuple

Point3 = Tuple[float, float, float]


@dataclass(frozen=True)
class DrapeVisualMetrics:
    vertices: int
    bounds: Tuple[float, float, float, float, float, float]
    spans: Tuple[float, float, float]
    centroid: Point3
    vertical_span_ratio: float
    lateral_span_ratio: float
    target_vertex_clearance: float | None
    finite: bool
    state: str


def _bounds(vertices: Sequence[Point3]) -> Tuple[float, float, float, float, float, float]:
    if not vertices:
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    xs = [float(v[0]) for v in vertices]
    ys = [float(v[1]) for v in vertices]
    zs = [float(v[2]) for v in vertices]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


def _centroid(vertices: Sequence[Point3]) -> Point3:
    count = float(len(vertices))
    return tuple(sum(float(v[i]) for v in vertices) / count for i in range(3))  # type: ignore[return-value]


def minimum_vertex_distance(source: Sequence[Point3], target: Sequence[Point3]) -> float | None:
    if not source or not target:
        return None
    best = float("inf")
    for a in source:
        for b in target:
            d2 = sum((float(a[i]) - float(b[i])) ** 2 for i in range(3))
            if d2 < best:
                best = d2
    return sqrt(best) if isfinite(best) else None


def inspect_drape(
    garment_vertices: Sequence[Point3],
    target_vertices: Sequence[Point3],
    *,
    target_height: float | None = None,
    target_width: float | None = None,
) -> DrapeVisualMetrics:
    """Return deterministic structural evidence for a generated drape.

    This is deliberately diagnostic rather than prescriptive: it does not
    claim that a geometrically plausible drape is physically correct.
    """
    if not garment_vertices:
        return DrapeVisualMetrics(0, (0.0,) * 6, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 0.0, 0.0, None, False, "empty")
    finite = all(isfinite(float(c)) for v in garment_vertices for c in v)
    if not finite:
        return DrapeVisualMetrics(len(garment_vertices), _bounds(garment_vertices), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 0.0, 0.0, None, False, "nonfinite")

    b = _bounds(garment_vertices)
    spans = (b[1] - b[0], b[3] - b[2], b[5] - b[4])
    vertical = max(spans)
    lateral = sorted(spans)[:2]
    lateral_width = lateral[1]
    vertical_span_ratio = vertical / float(target_height) if target_height and target_height > 0 else 0.0
    lateral_span_ratio = lateral_width / float(target_width) if target_width and target_width > 0 else 0.0
    clearance = minimum_vertex_distance(garment_vertices, target_vertices)
    centroid = _centroid(garment_vertices)

    state = "structurally-plausible"
    if vertical <= 1e-9:
        state = "flat-or-collapsed"
    elif target_height and vertical_span_ratio < 0.15:
        state = "short-drape-candidate"
    elif clearance is not None and target_width and clearance > max(float(target_width) * 0.30, 1.0):
        state = "detached-candidate"

    return DrapeVisualMetrics(
        len(garment_vertices), b, spans, centroid,
        vertical_span_ratio, lateral_span_ratio, clearance,
        True, state,
    )


def summarize(metrics: DrapeVisualMetrics) -> dict:
    return {
        "state": metrics.state,
        "vertices": metrics.vertices,
        "bounds": metrics.bounds,
        "spans": metrics.spans,
        "centroid": metrics.centroid,
        "vertical_span_ratio": metrics.vertical_span_ratio,
        "lateral_span_ratio": metrics.lateral_span_ratio,
        "target_vertex_clearance": metrics.target_vertex_clearance,
        "finite": metrics.finite,
    }
