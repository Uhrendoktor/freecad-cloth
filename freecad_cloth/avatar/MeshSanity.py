# Copyright (C) 2026 FreeCAD Cloth contributors
"""Helpers for compacting avatar meshes and orienting collision surfaces."""

from __future__ import annotations


from freecad_cloth.shared.mesh_topology import orient_closed_triangle_winding
from typing import TYPE_CHECKING

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
    used = sorted({int(i) for tri in triangles for i in tri})
    remap = {old: new for new, old in enumerate(used)}
    compact_vertices = tuple(vertices[i] for i in used)
    compact_triangles = tuple(tuple(remap[int(i)] for i in tri) for tri in triangles)
    return compact_vertices, compact_triangles
