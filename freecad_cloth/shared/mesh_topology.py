# Copyright (C) 2026 FreeCAD Cloth contributors
"""Topology utilities for collision surfaces shared across geometry adapters."""

from collections.abc import Sequence
from functools import lru_cache

import numpy as np


@lru_cache(maxsize=8)
def _closed_mesh_orientation_plan(
    triangles: tuple[tuple[int, int, int], ...],
) -> tuple[
    tuple[tuple[int, int, int], ...],
    tuple[tuple[int, ...], ...],
]:
    """Cache coherent triangle winding and connected components by topology.

    Vertex coordinates are intentionally excluded from this plan. Fitted avatar
    shapes retain stable indexed topology, so their graph traversal need only be
    calculated once per FreeCAD process.
    """
    edge_owners: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for face_index, (a, b, c) in enumerate(triangles):
        for first, second in ((a, b), (b, c), (c, a)):
            if first == second:
                msg = "closed mesh contains a degenerate indexed edge"
                raise ValueError(msg)
            edge = (min(first, second), max(first, second))
            direction = 1 if first < second else -1
            edge_owners.setdefault(edge, []).append((face_index, direction))

    if any(len(owners) != 2 for owners in edge_owners.values()):
        msg = "closed mesh requires every undirected edge to appear exactly twice"
        raise ValueError(msg)

    adjacency: list[list[tuple[int, bool]]] = [[] for _ in range(len(triangles))]
    for owners in edge_owners.values():
        (left, left_direction), (right, right_direction) = owners
        must_flip = left_direction == right_direction
        adjacency[left].append((right, must_flip))
        adjacency[right].append((left, must_flip))

    flip_state = [-1] * len(triangles)
    components: list[list[int]] = []
    for start in range(len(triangles)):
        if flip_state[start] >= 0:
            continue
        flip_state[start] = 0
        component: list[int] = []
        pending = [start]
        while pending:
            current = pending.pop()
            component.append(current)
            for neighbour, toggle in adjacency[current]:
                required = flip_state[current] ^ int(toggle)
                if flip_state[neighbour] < 0:
                    flip_state[neighbour] = required
                    pending.append(neighbour)
                elif flip_state[neighbour] != required:
                    msg = "closed mesh triangle winding is not orientable"
                    raise ValueError(msg)
        components.append(component)

    corrected = [list(face) for face in triangles]
    for face_index, should_flip in enumerate(flip_state):
        if should_flip:
            corrected[face_index][1], corrected[face_index][2] = (
                corrected[face_index][2],
                corrected[face_index][1],
            )
    corrected_faces = tuple((int(face[0]), int(face[1]), int(face[2])) for face in corrected)
    return corrected_faces, tuple(tuple(component) for component in components)


def orient_closed_triangle_winding(
    vertices: Sequence[Sequence[float]],
    triangles: Sequence[Sequence[int]],
) -> tuple[tuple[int, int, int], ...]:
    """Return closed manifold triangles with consistent, outward face winding.

    Vertex and face indices remain stable. An adjacent-face walk fixes local flips
    from source assets, then signed volume selects the outward orientation per
    connected component. Open, non-manifold, degenerate, or non-orientable inputs
    are rejected rather than silently weakening collision-surface validation.
    """
    points = np.asarray(vertices, dtype=np.float64)
    faces = np.asarray(triangles, dtype=np.int64)
    if points.ndim != 2 or points.shape[1] != 3 or not len(points):
        msg = "closed mesh vertices must have shape (N, 3)"
        raise ValueError(msg)
    if faces.ndim != 2 or faces.shape[1] != 3 or not len(faces):
        msg = "closed mesh triangles must have shape (M, 3)"
        raise ValueError(msg)
    if not bool(np.isfinite(points).all()):
        msg = "closed mesh vertices must be finite"
        raise ValueError(msg)
    if bool(np.any(faces < 0) or np.any(faces >= len(points))):
        msg = "closed mesh triangle index is outside the vertex array"
        raise ValueError(msg)

    topology = tuple(tuple(int(index) for index in face) for face in faces.tolist())
    coherent_faces, components = _closed_mesh_orientation_plan(topology)
    corrected = np.asarray(coherent_faces, dtype=np.int64)
    for component in components:
        component_indices = np.asarray(component, dtype=np.int64)
        component_faces = corrected[component_indices]
        component_points = points[component_faces]
        signed_volume6 = float(
            np.einsum(
                "ij,ij->i",
                component_points[:, 0],
                np.cross(component_points[:, 1], component_points[:, 2]),
            ).sum(dtype=np.float64)
        )
        used = np.unique(component_faces)
        extent = float(np.ptp(points[used], axis=0).max())
        if abs(signed_volume6) <= max(1e-18, extent**3 * 1e-12):
            msg = "closed mesh component has no reliable enclosed volume"
            raise ValueError(msg)
        if signed_volume6 < 0.0:
            second = corrected[component_indices, 1].copy()
            corrected[component_indices, 1] = corrected[component_indices, 2]
            corrected[component_indices, 2] = second
    return tuple((int(face[0]), int(face[1]), int(face[2])) for face in corrected.tolist())
