"""Optional non-authoritative mesh validation helpers.

This module deliberately does not make trimesh a runtime dependency.  The
adapter is downstream of PatternIR/ClothSystem/DrapeTarget and is intended
for acceptance diagnostics, backend comparisons, and developer tooling.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from importlib import import_module
from math import dist, isfinite

from freecad_cloth.common.ValidationModels import MeshArrays, validate_points3d

Point3 = tuple[float, float, float]
Triangle = tuple[int, int, int]


@dataclass(frozen=True)
class MeshValidationResult:
    """Deterministic derived-mesh health metrics."""

    vertices: int
    faces: int
    components: int
    bounds: tuple[float, float, float, float, float, float]
    surface_area: float
    watertight: bool | None
    finite: bool
    degenerate_faces: int


def _validate_arrays(
    vertices: Sequence[Point3], triangles: Sequence[Triangle]
) -> MeshArrays:
    """Validate mesh coordinates and connectivity with one schema boundary."""
    return MeshArrays.model_validate({"vertices": vertices, "triangles": triangles})


def _fallback_bounds(vertices: Sequence[Point3]) -> tuple[float, float, float, float, float, float]:
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

    # Mesh components are connected through shared edges, not just shared
    # vertices. Vertex-only adjacency incorrectly merges shells touching at a point.
    first_face_by_edge: dict[tuple[int, int], int] = {}
    for face_index, (a, b, c) in enumerate(triangles):
        for left, right in ((a, b), (b, c), (c, a)):
            edge = (min(left, right), max(left, right))
            previous_face = first_face_by_edge.get(edge)
            if previous_face is None:
                first_face_by_edge[edge] = face_index
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
    validated = _validate_arrays(vertices, triangles)
    vertices, triangles = validated.vertices, validated.triangles
    degenerate = sum(1 for a, b, c in triangles if len({a, b, c}) < 3)

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
            surface_area = float(mesh.area)
            if not isfinite(surface_area):
                raise ValueError("computed mesh surface area must be finite")
            return MeshValidationResult(
                vertices=len(vertices),
                faces=len(triangles),
                components=len(mesh.split(only_watertight=False)),
                bounds=(
                    float(bounds[0][0]),
                    float(bounds[1][0]),
                    float(bounds[0][1]),
                    float(bounds[1][1]),
                    float(bounds[0][2]),
                    float(bounds[1][2]),
                ),
                surface_area=surface_area,
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


def _nearest_target_clearance_bruteforce(
    garment_vertices: Sequence[Point3],
    target_vertices: Sequence[Point3],
) -> float:
    """Reference calculation and fallback for small or unsupported point clouds."""
    clearance = min(
        dist(source, candidate)
        for source in garment_vertices
        for candidate in target_vertices
    )
    if not isfinite(clearance):
        raise ValueError("computed vertex clearance must be finite")
    return clearance


def nearest_target_clearance(
    garment_vertices: Sequence[Point3],
    target_vertices: Sequence[Point3],
) -> float:
    """Return minimum Euclidean vertex clearance.

    For larger point clouds, SciPy's exact cKDTree query avoids the quadratic
    pairwise scan. SciPy remains optional. Small inputs use the scalar reference
    implementation to avoid tree-construction overhead; unsupported/extreme
    numeric inputs fall back to the reference path, which retains fail-closed
    finite-distance validation.
    """
    garment = validate_points3d(garment_vertices)
    target = validate_points3d(target_vertices)
    if not garment or not target:
        raise ValueError("garment and target vertices are required")

    # Below this threshold, constructing a spatial index is usually more work
    # than the direct comparison. The threshold is a performance choice only.
    if len(garment) * len(target) < 1024:
        return _nearest_target_clearance_bruteforce(garment, target)

    try:
        spatial = import_module("scipy.spatial")
    except ImportError:
        return _nearest_target_clearance_bruteforce(garment, target)

    tree_type = getattr(spatial, "cKDTree", None)
    if tree_type is None:
        return _nearest_target_clearance_bruteforce(garment, target)

    try:
        distances, _ = tree_type(target).query(garment, k=1, eps=0.0, workers=1)
        clearance = min(float(value) for value in distances)
    except (OverflowError, ValueError, RuntimeError):
        return _nearest_target_clearance_bruteforce(garment, target)

    # cKDTree can return infinity for a finite but unrepresentable distance.
    # The scalar reference provides the canonical error behavior for that case.
    if not isfinite(clearance):
        return _nearest_target_clearance_bruteforce(garment, target)
    return clearance

def nearest_surface_clearance(
    garment_vertices: Sequence[Point3],
    target_vertices: Sequence[Point3],
    target_triangles: Sequence[Triangle],
) -> float:
    """Return minimum point-to-surface distance using trimesh when available."""
    validated = _validate_arrays(target_vertices, target_triangles)
    garment_vertices = validate_points3d(garment_vertices)
    target_vertices, target_triangles = validated.vertices, validated.triangles
    if not garment_vertices:
        raise ValueError("garment vertices are required")
    if not target_triangles:
        raise ValueError("target triangles are required")
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
    if not len(distances):
        raise ValueError("surface clearance produced no distance results")
    clearance = float(np.min(distances))
    if not isfinite(clearance):
        raise ValueError("computed surface clearance must be finite")
    return clearance
