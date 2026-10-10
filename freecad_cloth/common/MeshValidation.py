"""Optional non-authoritative mesh validation helpers.

This module deliberately does not make trimesh a runtime dependency.  The
adapter is downstream of PatternIR/ClothSystem/DrapeTarget and is intended
for acceptance diagnostics, backend comparisons, and developer tooling.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from math import isfinite
from numbers import Real
from typing import cast

import numpy as np
from numpy.typing import NDArray
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import KDTree

from freecad_cloth.common.ValidationModels import MeshArrays, MeshHealthMetrics, validate_points3d

Point3 = tuple[float, float, float]
Triangle = tuple[int, int, int]


MeshValidationResult = MeshHealthMetrics

def _validate_arrays(vertices: Sequence[Point3], triangles: Sequence[Triangle]) -> MeshArrays:
    """Validate mesh coordinates and connectivity with one schema boundary."""
    return MeshArrays.model_validate({"vertices": vertices, "triangles": triangles})


def _fallback_bounds(vertices: Sequence[Point3]) -> tuple[float, float, float, float, float, float]:
    if not vertices:
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    xs = [float(vertex[0]) for vertex in vertices]
    ys = [float(vertex[1]) for vertex in vertices]
    zs = [float(vertex[2]) for vertex in vertices]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


def _triangle_areas(
    vertices: Sequence[Point3], triangles: Sequence[Triangle]
) -> NDArray[np.float64]:
    """Calculate triangle areas with NumPy's vectorized cross product and norm."""
    coordinates = np.asarray(vertices, dtype=np.float64).reshape((-1, 3))
    faces = np.asarray(triangles, dtype=np.intp).reshape((-1, 3))
    with np.errstate(over="ignore", invalid="ignore"):
        cross_products = np.cross(
            coordinates[faces[:, 1]] - coordinates[faces[:, 0]],
            coordinates[faces[:, 2]] - coordinates[faces[:, 0]],
        )
        areas = np.asarray(0.5 * np.linalg.norm(cross_products, axis=1), dtype=np.float64)
    if not bool(np.isfinite(areas).all()):
        raise ValueError("computed mesh surface area must be finite")
    return areas


def _fallback_surface_area(areas: NDArray[np.float64]) -> float:
    """Sum precomputed triangle areas without requiring the optional trimesh package."""
    with np.errstate(over="ignore", invalid="ignore"):
        total = float(np.sum(areas, dtype=np.float64))
    if not isfinite(total):
        raise ValueError("computed mesh surface area must be finite")
    return total


def _fallback_components(triangles: Sequence[Triangle]) -> int:
    """Count edge-connected face components using SciPy's sparse graph algorithm."""
    if not triangles:
        return 0
    first_face_by_edge: dict[tuple[int, int], int] = {}
    rows: list[int] = []
    columns: list[int] = []
    for face_index, (a, b, c) in enumerate(triangles):
        for left, right in ((a, b), (b, c), (c, a)):
            edge = (min(left, right), max(left, right))
            previous_face = first_face_by_edge.get(edge)
            if previous_face is None:
                first_face_by_edge[edge] = face_index
            else:
                rows.extend((previous_face, face_index))
                columns.extend((face_index, previous_face))
    if not rows:
        return len(triangles)
    adjacency = coo_matrix(
        (np.ones(len(rows), dtype=np.uint8), (rows, columns)),
        shape=(len(triangles), len(triangles)),
    ).tocsr()
    count, _ = connected_components(adjacency, directed=False, return_labels=True)
    return int(count)


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
    triangle_areas = _triangle_areas(vertices, triangles)
    degenerate = sum(
        1
        for triangle, area in zip(triangles, triangle_areas, strict=True)
        if len(set(triangle)) < 3 or area == 0.0
    )

    if prefer_trimesh:
        try:
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
        surface_area=_fallback_surface_area(triangle_areas),
        watertight=None,
        finite=True,
        degenerate_faces=degenerate,
    )


def nearest_target_clearance(
    garment_vertices: Sequence[Point3],
    target_vertices: Sequence[Point3],
) -> float:
    """Return the minimum Euclidean distance between two validated 3D vertex sets.

    SciPy's exact KDTree query is the single production implementation. Coordinates
    are validated before indexing, and an unrepresentable result fails closed.
    """
    garment = validate_points3d(cast(Iterable[Iterable[Real]], garment_vertices))
    target = validate_points3d(cast(Iterable[Iterable[Real]], target_vertices))
    if not garment or not target:
        raise ValueError("garment and target vertices are required")

    try:
        distances, _ = KDTree(target).query(garment, k=1, eps=0.0, workers=1)
        clearance = min(float(value) for value in distances)
    except (OverflowError, ValueError, RuntimeError) as exc:
        raise ValueError("could not calculate finite nearest vertex clearance") from exc
    if not isfinite(clearance):
        raise ValueError("computed vertex clearance must be finite")
    return clearance


def nearest_surface_clearance(
    garment_vertices: Sequence[Point3],
    target_vertices: Sequence[Point3],
    target_triangles: Sequence[Triangle],
) -> float:
    """Return minimum point-to-surface distance using trimesh when available."""
    validated = _validate_arrays(target_vertices, target_triangles)
    garment_vertices = validate_points3d(cast(Iterable[Iterable[Real]], garment_vertices))
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
