# Copyright (C) 2026 FreeCAD Cloth contributors
"""Non-authoritative mesh validation helpers backed by external libraries.

Trimesh is a required runtime dependency for nearest-surface clearance and
accelerated diagnostics. A NumPy/SciPy fallback preserves basic mesh-health
metrics for isolated tooling environments where Trimesh is unavailable.
The adapter is downstream of PatternIR/ClothSystem/DrapeTarget and is intended
for acceptance diagnostics, backend comparisons, and developer tooling.
"""

from __future__ import annotations

from math import isfinite
from typing import TYPE_CHECKING, cast

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import KDTree

from freecad_cloth.common.ValidationModels import MeshArrays, MeshHealthMetrics, validate_points3d

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from numbers import Real
    from numpy.typing import NDArray

Point3 = tuple[float, float, float]
Triangle = tuple[int, int, int]


MeshValidationResult = MeshHealthMetrics


def _validate_arrays(vertices: Sequence[Point3], triangles: Sequence[Triangle]) -> MeshArrays:
    """Validate mesh coordinates and connectivity with one schema boundary."""
    return MeshArrays.model_validate({"vertices": vertices, "triangles": triangles})


def _fallback_bounds(
    vertices: Sequence[Point3],
) -> tuple[float, float, float, float, float, float]:
    """Compute axis-aligned bounds with NumPy when Trimesh is unavailable.

    Args:
        vertices: Finite 3D vertex coordinates.

    Returns:
        Minimum and maximum coordinates ordered as X, Y, and Z pairs.
        Empty input returns six zeroes to preserve the diagnostic contract.
    """
    if not vertices:
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    coordinates = np.asarray(vertices, dtype=np.float64).reshape((-1, 3))
    minimums = coordinates.min(axis=0)
    maximums = coordinates.max(axis=0)
    return (
        float(minimums[0]),
        float(maximums[0]),
        float(minimums[1]),
        float(maximums[1]),
        float(minimums[2]),
        float(maximums[2]),
    )


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
        msg = "computed mesh surface area must be finite"
        raise ValueError(msg)
    return areas


def _fallback_surface_area(areas: NDArray[np.float64]) -> float:
    """Sum precomputed triangle areas without requiring the optional trimesh package."""
    with np.errstate(over="ignore", invalid="ignore"):
        total = float(np.sum(areas, dtype=np.float64))
    if not isfinite(total):
        msg = "computed mesh surface area must be finite"
        raise ValueError(msg)
    return total


def _fallback_components(triangles: Sequence[Triangle]) -> int:
    """Count edge-connected face components using SciPy's sparse graph algorithm.

    Args:
        triangles: Validated triangle vertex indices.

    Returns:
        The number of edge-connected face components.
    """
    faces = np.asarray(triangles, dtype=np.intp).reshape((-1, 3))
    face_count = len(faces)
    if face_count == 0:
        return 0

    edges = np.concatenate(
        (faces[:, (0, 1)], faces[:, (1, 2)], faces[:, (2, 0)]),
        axis=0,
    )
    edges.sort(axis=1)
    owners = np.tile(np.arange(face_count, dtype=np.intp), 3)
    order = np.lexsort((owners, edges[:, 1], edges[:, 0]))
    sorted_edges = edges[order]
    sorted_owners = owners[order]
    shared_edge = np.all(sorted_edges[1:] == sorted_edges[:-1], axis=1)
    connected_pair = shared_edge & (sorted_owners[1:] != sorted_owners[:-1])
    rows = sorted_owners[:-1][connected_pair]
    columns = sorted_owners[1:][connected_pair]
    if not rows.size:
        return int(face_count)

    row_indices = np.concatenate((rows, columns))
    column_indices = np.concatenate((columns, rows))
    adjacency = coo_matrix(
        (np.ones(len(row_indices), dtype=np.uint8), (row_indices, column_indices)),
        shape=(face_count, face_count),
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

    ``trimesh`` is imported lazily. The fallback keeps basic metrics available
    in isolated tooling environments where the package is unavailable.
    """
    validated = _validate_arrays(vertices, triangles)
    vertices, triangles = validated.vertices, validated.triangles
    triangle_areas = _triangle_areas(vertices, triangles)
    faces = np.asarray(triangles, dtype=np.intp).reshape((-1, 3))
    unique_vertices = (
        (faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]) & (faces[:, 2] != faces[:, 0])
    )
    degenerate = int(np.count_nonzero(~unique_vertices | (triangle_areas == 0.0)))

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
                msg = "computed mesh surface area must be finite"
                raise ValueError(msg)
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


def nearest_target_observation(
    garment_vertices: Sequence[Point3],
    target_vertices: Sequence[Point3],
) -> tuple[float, Point3]:
    """Return the nearest target vertex and its exact distance to the garment.

    Args:
        garment_vertices: Garment points expressed in the target's coordinate frame.
        target_vertices: Target mesh vertex coordinates.

    Returns:
        The minimum Euclidean distance and the target vertex at that minimum.

    Raises:
        ValueError: If either point set is empty or the query produces a non-finite distance.
    """
    garment = validate_points3d(cast("Iterable[Iterable[Real]]", garment_vertices))
    target = validate_points3d(cast("Iterable[Iterable[Real]]", target_vertices))
    if not garment or not target:
        msg = "garment and target vertices are required"
        raise ValueError(msg)

    try:
        distances, target_indices = KDTree(target).query(garment, k=1, eps=0.0, workers=1)
        garment_index = int(np.argmin(distances))
        target_index = int(target_indices[garment_index])
        clearance = float(distances[garment_index])
        target_point = target[target_index]
    except (IndexError, OverflowError, ValueError, RuntimeError) as exc:
        msg = "could not calculate finite nearest vertex observation"
        raise ValueError(msg) from exc
    if not isfinite(clearance):
        msg = "computed vertex clearance must be finite"
        raise ValueError(msg)
    return clearance, (float(target_point[0]), float(target_point[1]), float(target_point[2]))


def nearest_target_clearance(
    garment_vertices: Sequence[Point3],
    target_vertices: Sequence[Point3],
) -> float:
    """Return the minimum Euclidean distance between two validated 3D vertex sets.

    Args:
        garment_vertices: Garment points in the target's coordinate frame.
        target_vertices: Target mesh points.

    Returns:
        The exact minimum vertex-to-vertex clearance in millimetres.

    Raises:
        ValueError: If either point set is empty or the query result is non-finite.
    """
    clearance, _target_point = nearest_target_observation(garment_vertices, target_vertices)
    return clearance


def nearest_surface_clearance(
    garment_vertices: Sequence[Point3],
    target_vertices: Sequence[Point3],
    target_triangles: Sequence[Triangle],
) -> float:
    """Return minimum point-to-surface distance using Trimesh and Rtree."""
    validated = _validate_arrays(target_vertices, target_triangles)
    garment_vertices = validate_points3d(cast("Iterable[Iterable[Real]]", garment_vertices))
    target_vertices, target_triangles = validated.vertices, validated.triangles
    if not garment_vertices:
        msg = "garment vertices are required"
        raise ValueError(msg)
    if not target_triangles:
        msg = "target triangles are required"
        raise ValueError(msg)
    try:
        import numpy as np
        import trimesh
    except ImportError as exc:
        msg = "trimesh is required for nearest_surface_clearance"
        raise RuntimeError(msg) from exc
    mesh = trimesh.Trimesh(
        vertices=np.asarray(target_vertices, dtype=float),
        faces=np.asarray(target_triangles, dtype=int),
        process=False,
    )
    _, distances, _ = mesh.nearest.on_surface(np.asarray(garment_vertices, dtype=float))
    if not len(distances):
        msg = "surface clearance produced no distance results"
        raise ValueError(msg)
    clearance = float(np.min(distances))
    if not isfinite(clearance):
        msg = "computed surface clearance must be finite"
        raise ValueError(msg)
    return clearance
