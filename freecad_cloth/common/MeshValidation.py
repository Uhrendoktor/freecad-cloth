"""Optional non-authoritative mesh validation helpers.

This module deliberately does not make trimesh a runtime dependency.  The
adapter is downstream of PatternIR/SimulationScene/DrapeTarget and is intended
for acceptance diagnostics, backend comparisons, and developer tooling.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
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


def _fallback_components(triangles: Sequence[Triangle]) -> int:
    """Count face-connected components without optional dependencies."""
    if not triangles:
        return 0

    parent = list(range(len(triangles)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    first_face_by_vertex: dict[int, int] = {}
    for face_index, triangle in enumerate(triangles):
        for vertex_index in triangle:
            vertex_index = int(vertex_index)
            previous_face = first_face_by_vertex.get(vertex_index)
            if previous_face is None:
                first_face_by_vertex[vertex_index] = face_index
            else:
                union(face_index, previous_face)

    return len({find(index) for index in range(len(triangles))})


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
        components=_fallback_components(triangles),
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
