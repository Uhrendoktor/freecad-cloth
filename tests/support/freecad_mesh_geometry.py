# Copyright (C) 2026 FreeCAD Cloth contributors
"""Vectorized mesh-coordinate helpers for standalone FreeCAD acceptance tests."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import numpy as np

_TOP_EDGE_TOLERANCE_MM = 1e-9
_MIN_PIN_COUNT = 2


def opposite_top_edge_vertices(
    mesh_positions: Sequence[Sequence[float]],
    boundary: Iterable[Iterable[int]],
    minimum_span_mm: float,
) -> tuple[tuple[int, int], float]:
    """Select opposite vertices from the top horizontal boundary of a mesh.

    Args:
        mesh_positions: Mesh-local coordinates, ordered as X, Y, and Z.
        boundary: Boundary chains containing mesh-local vertex indices.
        minimum_span_mm: Minimum acceptable horizontal distance between the pins.

    Returns:
        The leftmost and rightmost top-edge vertex indices and their X span.

    Raises:
        RuntimeError: If the mesh has no boundary, fewer than two top vertices,
            or a top-edge span smaller than the required minimum.
    """
    coordinates = np.asarray(mesh_positions, dtype=np.float64).reshape((-1, 3))
    boundary_indices = np.fromiter(
        (int(index) for chain in boundary for index in chain),
        dtype=np.intp,
    )
    if not boundary_indices.size:
        msg = "blanket quality mesh has no boundary vertices"
        raise RuntimeError(msg)
    boundary_indices = np.unique(boundary_indices)
    boundary_y = coordinates[boundary_indices, 1]
    top_y = float(np.max(boundary_y))
    top_indices = boundary_indices[
        np.abs(boundary_y - top_y) <= _TOP_EDGE_TOLERANCE_MM
    ]
    if top_indices.size < _MIN_PIN_COUNT:
        msg = "blanket top edge has fewer than two boundary vertices"
        raise RuntimeError(msg)
    top_x = coordinates[top_indices, 0]
    left_index = int(top_indices[int(np.argmin(top_x))])
    right_index = int(top_indices[int(np.argmax(top_x))])
    span_mm = abs(float(coordinates[right_index, 0] - coordinates[left_index, 0]))
    if span_mm < minimum_span_mm:
        msg = f"blanket pins are not opposite top-edge corners: span={span_mm:.3f}"
        raise RuntimeError(msg)
    return (left_index, right_index), span_mm
