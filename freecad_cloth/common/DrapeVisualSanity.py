"""Solver-neutral visual sanity metrics for generated garment drapes."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt
from statistics import median
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


def seam_correspondence_gap(
    boundary_a: Sequence[Point3],
    boundary_b: Sequence[Point3],
    edge_a: int,
    edge_b: int,
    *,
    reversed_b: bool = False,
    start_a: float = 0.0,
    end_a: float = 1.0,
    start_b: float = 0.0,
    end_b: float = 1.0,
    samples: int = 5,
) -> float:
    """Return deterministic max positional gap along one authored seam correspondence."""
    if not boundary_a or not boundary_b:
        raise ValueError("seam boundaries are required")
    if samples < 2:
        raise ValueError("at least two seam samples are required")
    if not 0 <= int(edge_a) < len(boundary_a) or not 0 <= int(edge_b) < len(boundary_b):
        raise ValueError("seam edge index is out of range")
    a0 = boundary_a[int(edge_a)]
    a1 = boundary_a[(int(edge_a) + 1) % len(boundary_a)]
    b0 = boundary_b[int(edge_b)]
    b1 = boundary_b[(int(edge_b) + 1) % len(boundary_b)]
    if reversed_b:
        b0, b1 = b1, b0
        start_b, end_b = 1.0 - float(end_b), 1.0 - float(start_b)

    def interpolate(left: Point3, right: Point3, fraction: float) -> Point3:
        return tuple(
            float(left[i]) + (float(right[i]) - float(left[i])) * fraction
            for i in range(3)
        )  # type: ignore[return-value]

    maximum = 0.0
    for sample in range(int(samples)):
        fraction = sample / float(samples - 1)
        point_a = interpolate(a0, a1, float(start_a) + (float(end_a) - float(start_a)) * fraction)
        point_b = interpolate(b0, b1, float(start_b) + (float(end_b) - float(start_b)) * fraction)
        gap = sqrt(sum((point_a[i] - point_b[i]) ** 2 for i in range(3)))
        maximum = max(maximum, gap)
    return maximum


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

    Coordinates follow the FreeCAD garment convention used by the canonical
    visual fixture: X/Y form the garment footprint and Z is vertical. The
    ratios therefore intentionally use Z for vertical coverage and the larger
    of X/Y for lateral coverage; using the largest or second-smallest axis can
    make a wide, flattened or side-on garment look healthy by mistake.
    """
    if not garment_vertices:
        return DrapeVisualMetrics(0, (0.0,) * 6, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 0.0, 0.0, None, False, "empty")
    finite = all(isfinite(float(c)) for v in garment_vertices for c in v)
    if not finite:
        return DrapeVisualMetrics(len(garment_vertices), _bounds(garment_vertices), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 0.0, 0.0, None, False, "nonfinite")

    b = _bounds(garment_vertices)
    spans = (b[1] - b[0], b[3] - b[2], b[5] - b[4])
    vertical = spans[2]
    lateral_width = max(spans[0], spans[1])
    vertical_span_ratio = vertical / float(target_height) if target_height and target_height > 0 else 0.0
    lateral_span_ratio = lateral_width / float(target_width) if target_width and target_width > 0 else 0.0
    clearance = minimum_vertex_distance(garment_vertices, target_vertices)
    centroid = _centroid(garment_vertices)

    state = "structurally-plausible"
    if not target_vertices:
        state = "missing-target"
    elif vertical <= 1e-9:
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


_FATAL_VISUAL_STATES = frozenset({"detached-candidate"})
_FATAL_VISUAL_DIAGNOSTICS = frozenset(
    {"lateral-detached-candidate", "collapsed-candidate", "below-hem-candidate"}
)


def assert_drape_diagnostics(records: Sequence[dict]) -> None:
    """Fail closed when existing rendered-drape diagnostics contradict acceptance."""
    failures = []
    for record in records:
        classification = record.get("failure_classification", {})
        state = str(classification.get("state", ""))
        diagnostics = {str(item) for item in record.get("diagnostics", ())}
        fatal = state in _FATAL_VISUAL_STATES or bool(diagnostics & _FATAL_VISUAL_DIAGNOSTICS)
        if fatal:
            failures.append(
                "%s: classification=%s diagnostics=%s"
                % (
                    str(record.get("panel", "<unknown>")),
                    state or "none",
                    ",".join(sorted(diagnostics)),
                )
            )
    if failures:
        raise RuntimeError(
            "drape visual acceptance failed closed: " + "; ".join(failures)
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



def mesh_shape_sanity(vertices, triangles):
    """Return deterministic mesh-shape health metrics for visual regression.

    The metrics intentionally describe geometry rather than deciding whether a
    cloth result is physically correct. They catch the two failure modes that
    are easy to miss in a camera-only regression: isolated long-edge spikes
    and an unexpectedly extreme lateral footprint.
    """
    if not vertices:
        return {
            "finite": False,
            "vertices": 0,
            "faces": 0,
            "median_edge_length": 0.0,
            "max_edge_length": 0.0,
            "edge_spike_ratio": float("inf"),
            "spike_edge_fraction": 1.0,
            "footprint_aspect_ratio": float("inf"),
        }

    finite = all(isfinite(float(c)) for vertex in vertices for c in vertex)
    if not finite:
        return {
            "finite": False,
            "vertices": len(vertices),
            "faces": len(triangles),
            "median_edge_length": 0.0,
            "max_edge_length": 0.0,
            "edge_spike_ratio": float("inf"),
            "spike_edge_fraction": 1.0,
            "footprint_aspect_ratio": float("inf"),
        }

    unique_edges = set()
    lengths = []
    for triangle in triangles:
        if len(triangle) != 3:
            continue
        a, b, c = (int(index) for index in triangle)
        for left, right in ((a, b), (b, c), (c, a)):
            edge = (min(left, right), max(left, right))
            if edge in unique_edges:
                continue
            unique_edges.add(edge)
            p = vertices[left]
            q = vertices[right]
            lengths.append(sqrt(sum((float(p[i]) - float(q[i])) ** 2 for i in range(3))))

    if not lengths:
        median_edge = 0.0
        max_edge = 0.0
        spike_ratio = float("inf")
        spike_fraction = 1.0
    else:
        median_edge = float(median(lengths))
        max_edge = float(max(lengths))
        spike_ratio = max_edge / median_edge if median_edge > 1e-12 else float("inf")
        spike_fraction = sum(1 for value in lengths if value > 4.0 * median_edge) / float(len(lengths))

    xs = [float(vertex[0]) for vertex in vertices]
    ys = [float(vertex[1]) for vertex in vertices]
    span_x = max(xs) - min(xs)
    span_y = max(ys) - min(ys)
    small = min(value for value in (span_x, span_y) if value > 1e-12) if max(span_x, span_y) > 1e-12 else 0.0
    aspect = max(span_x, span_y) / small if small > 0.0 else float("inf")

    return {
        "finite": True,
        "vertices": len(vertices),
        "faces": len(triangles),
        "median_edge_length": median_edge,
        "max_edge_length": max_edge,
        "edge_spike_ratio": spike_ratio,
        "spike_edge_fraction": spike_fraction,
        "footprint_aspect_ratio": aspect,
    }
