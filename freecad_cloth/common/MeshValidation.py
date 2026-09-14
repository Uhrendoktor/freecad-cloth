"""Optional non-authoritative mesh validation helpers.

This module deliberately does not make trimesh a runtime dependency.  The
adapter is downstream of PatternIR/SimulationScene/DrapeTarget and is intended
for acceptance diagnostics, backend comparisons, and developer tooling.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt
from typing import Sequence, Tuple

Point3 = Tuple[float, float, float]
Triangle = Tuple[int, int, int]


@dataclass(frozen=True)
class MeshValidationResult:
    """Deterministic derived-mesh health metrics."""

    vertices: int
    faces: int
    components: int
    bounds: Tuple[float, float, float, float, float, float]
    surface_area: float
    watertight: bool | None
    finite: bool
    degenerate_faces: int


@dataclass(frozen=True)
class DrapeVisualMetrics:
    """Solver-neutral garment-vs-target visual sanity measurements."""

    vertices: int
    bounds: Tuple[float, float, float, float, float, float]
    spans: Tuple[float, float, float]
    centroid: Point3
    vertical_span_ratio: float
    lateral_span_ratio: float
    target_vertex_clearance: float | None
    finite: bool
    state: str


def _validate_arrays(vertices: Sequence[Point3], triangles: Sequence[Triangle]) -> None:
    count = len(vertices)
    for vertex in vertices:
        if len(vertex) != 3 or not all(isfinite(float(value)) for value in vertex):
            raise ValueError("mesh vertices must be finite 3D points")
    for triangle in triangles:
        if len(triangle) != 3:
            raise ValueError("mesh triangles must contain exactly three indices")
        if any(int(index) < 0 or int(index) >= count for index in triangle):
            raise ValueError("mesh triangle index is out of range")


def _fallback_bounds(vertices: Sequence[Point3]) -> Tuple[float, float, float, float, float, float]:
    if not vertices:
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    xs = [float(vertex[0]) for vertex in vertices]
    ys = [float(vertex[1]) for vertex in vertices]
    zs = [float(vertex[2]) for vertex in vertices]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


def validate_mesh(
    vertices: Sequence[Point3],
    triangles: Sequence[Triangle],
    *,
    prefer_trimesh: bool = True,
) -> MeshValidationResult:
    """Return mesh-health metrics without mutating the source arrays.

    ``trimesh`` is imported lazily and remains optional. A deterministic
    Python fallback keeps the validator useful in the core test environment.
    """
    _validate_arrays(vertices, triangles)
    degenerate = sum(1 for a, b, c in triangles if len({int(a), int(b), int(c)}) < 3)

    if prefer_trimesh:
        try:
            import numpy as np
            import trimesh

            mesh = trimesh.Trimesh(
                vertices=np.asarray(vertices, dtype=float),
                faces=np.asarray(triangles, dtype=int),
                process=False,
            )
            bounds = mesh.bounds
            return MeshValidationResult(
                vertices=len(vertices),
                faces=len(triangles),
                components=len(mesh.split(only_watertight=False)),
                bounds=(
                    float(bounds[0][0]), float(bounds[1][0]),
                    float(bounds[0][1]), float(bounds[1][1]),
                    float(bounds[0][2]), float(bounds[1][2]),
                ),
                surface_area=float(mesh.area),
                watertight=bool(mesh.is_watertight),
                finite=bool(np.isfinite(mesh.vertices).all()),
                degenerate_faces=degenerate,
            )
        except ImportError:
            pass

    return MeshValidationResult(
        vertices=len(vertices),
        faces=len(triangles),
        components=1 if triangles else 0,
        bounds=_fallback_bounds(vertices),
        surface_area=0.0,
        watertight=None,
        finite=True,
        degenerate_faces=degenerate,
    )


def nearest_target_clearance(
    garment_vertices: Sequence[Point3],
    target_vertices: Sequence[Point3],
) -> float:
    """Return minimum garment-to-target vertex distance."""
    if not garment_vertices or not target_vertices:
        raise ValueError("garment and target vertices are required")
    best = float("inf")
    for source in garment_vertices:
        for target in target_vertices:
            distance = sum((float(a) - float(b)) ** 2 for a, b in zip(source, target))
            if distance < best:
                best = distance
    return best ** 0.5


def nearest_surface_clearance(
    garment_vertices: Sequence[Point3],
    target_vertices: Sequence[Point3],
    target_triangles: Sequence[Triangle],
) -> float:
    """Return minimum point-to-surface distance using trimesh when available."""
    _validate_arrays(target_vertices, target_triangles)
    if not garment_vertices:
        raise ValueError("garment vertices are required")
    try:
        import numpy as np
        import trimesh
    except ImportError as exc:
        raise RuntimeError("trimesh is required for nearest_surface_clearance") from exc
    mesh = trimesh.Trimesh(
        vertices=np.asarray(target_vertices, dtype=float),
        faces=np.asarray(target_triangles, dtype=int),
        process=False,
    )
    _, distances, _ = mesh.nearest.on_surface(np.asarray(garment_vertices, dtype=float))
    return float(np.min(distances)) if len(distances) else float("inf")


def _centroid(vertices: Sequence[Point3]) -> Point3:
    count = float(len(vertices))
    return tuple(sum(float(v[i]) for v in vertices) / count for i in range(3))  # type: ignore[return-value]


def measure_drape_visual_sanity(
    garment_vertices: Sequence[Point3],
    target_vertices: Sequence[Point3],
    *,
    target_height: float | None = None,
    target_width: float | None = None,
) -> DrapeVisualMetrics:
    """Measure deterministic garment-vs-target evidence without mutation.

    ``state`` is an evidence label only. It must not be interpreted as proof
    of physical correctness or solver quality.
    """
    if not garment_vertices:
        return DrapeVisualMetrics(
            0,
            (0.0,) * 6,
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
            0.0,
            0.0,
            None,
            False,
            "empty",
        )

    finite = all(isfinite(float(c)) for v in garment_vertices for c in v)
    if not finite:
        return DrapeVisualMetrics(
            len(garment_vertices),
            _fallback_bounds(garment_vertices),
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
            0.0,
            0.0,
            None,
            False,
            "nonfinite",
        )

    bounds = _fallback_bounds(garment_vertices)
    spans = (bounds[1] - bounds[0], bounds[3] - bounds[2], bounds[5] - bounds[4])
    vertical = max(spans)
    lateral_width = sorted(spans)[:2][1]
    vertical_ratio = vertical / float(target_height) if target_height and target_height > 0 else 0.0
    lateral_ratio = lateral_width / float(target_width) if target_width and target_width > 0 else 0.0
    clearance = None
    if target_vertices:
        clearance = nearest_target_clearance(garment_vertices, target_vertices)

    state = "structurally-plausible"
    if vertical <= 1e-9:
        state = "flat-or-collapsed"
    elif target_height and vertical_ratio < 0.15:
        state = "short-drape-candidate"
    elif clearance is not None and target_width and clearance > max(float(target_width) * 0.30, 1.0):
        state = "detached-candidate"

    return DrapeVisualMetrics(
        len(garment_vertices),
        bounds,
        spans,
        _centroid(garment_vertices),
        vertical_ratio,
        lateral_ratio,
        clearance,
        True,
        state,
    )


def summarize_drape_visual_metrics(metrics: DrapeVisualMetrics) -> dict:
    """Return a stable JSON-ready representation of drape metrics."""
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
