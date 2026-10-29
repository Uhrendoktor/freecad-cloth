# Copyright (C) 2026 FreeCAD Cloth contributors
"""Helpers for compacting avatar meshes and orienting collision surfaces."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from freecad_cloth.shared.MeshTopology import orient_closed_triangle_winding

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["compact_mesh", "orient_closed_triangle_winding"]


def compact_mesh(
    vertices: Sequence[tuple[float, float, float]],
    triangles: Sequence[tuple[int, int, int]],
) -> tuple[tuple[tuple[float, float, float], ...], tuple[tuple[int, int, int], ...]]:
    """Remove unused vertices and remap triangles to a compact mesh.

    Args:
        vertices: Ordered 3D points referenced by the triangle indices.
        triangles: Triangle index triples whose references are to be compacted.

    Returns:
        Compact vertex coordinates and remapped triangles, preserving source order.
    """
    vertex_array = np.asarray(vertices, dtype=np.float64).reshape((-1, 3))
    triangle_array = np.asarray(triangles, dtype=np.intp).reshape((-1, 3))
    used, inverse = np.unique(triangle_array.reshape(-1), return_inverse=True)
    compact_coordinates = vertex_array[used]
    compact_indices = inverse.reshape(triangle_array.shape)
    compact_vertices = tuple(
        (float(point[0]), float(point[1]), float(point[2])) for point in compact_coordinates
    )
    compact_triangles = tuple(
        (int(face[0]), int(face[1]), int(face[2])) for face in compact_indices
    )
    return compact_vertices, compact_triangles
