# Copyright (C) 2026 FreeCAD Cloth contributors
"""Topology utilities for collision surfaces shared across geometry adapters."""

from collections.abc import Sequence
from functools import lru_cache

import numpy as np


def triangle_indices_are_valid(
    triangles: Sequence[Sequence[object]],
    vertex_count: int,
) -> bool:
    """Return whether triangle connectivity is valid for the supplied vertices.

    Args:
        triangles: Raw triangle index data, expected to have shape (N, 3).
        vertex_count: Number of available vertices.

    Returns:
        Whether indices are integral, in range, and distinct within each face.
        Malformed array-like input returns False.
    """
    try:
        faces = np.asarray(triangles)
        return (
            faces.shape == (len(triangles), 3)
            and np.issubdtype(faces.dtype, np.integer)
            and bool(((faces >= 0) & (faces < vertex_count)).all())
            and bool(
                (
                    (faces[:, 0] != faces[:, 1])
                    & (faces[:, 1] != faces[:, 2])
                    & (faces[:, 0] != faces[:, 2])
                ).all()
            )
        )
    except (TypeError, ValueError, OverflowError, IndexError):
        return False


_EDGE_OWNER_COUNT = 2
_TRIANGLE_VERTEX_COUNT = 3
_COORDINATE_DIMENSIONS = 3


def _edge_owners(
    triangles: tuple[tuple[int, int, int], ...],
) -> dict[tuple[int, int], list[tuple[int, int]]]:
    """Map undirected triangle edges to their owning faces and directions.

    Args:
        triangles: Ordered triangle connectivity used by the surface.

    Returns:
        Edge-to-face ownership mapping with each shared edge represented twice.

    Raises:
        ValueError: If a face has a degenerate edge or an edge lacks exactly two owners.
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

    if any(len(owners) != _EDGE_OWNER_COUNT for owners in edge_owners.values()):
        msg = "closed mesh requires every undirected edge to appear exactly twice"
        raise ValueError(msg)
    return edge_owners


def _face_adjacency(
    edge_owners: dict[tuple[int, int], list[tuple[int, int]]],
    face_count: int,
) -> list[list[tuple[int, bool]]]:
    """Build adjacent-face constraints from the validated edge owners.

    Args:
        edge_owners: Mapping where every undirected edge has exactly two owners.
        face_count: Number of faces that must be represented in the adjacency list.

    Returns:
        Per-face neighbors paired with whether their winding flips must differ.
    """
    adjacency: list[list[tuple[int, bool]]] = [[] for _ in range(face_count)]
    for owners in edge_owners.values():
        (left, left_direction), (right, right_direction) = owners
        must_flip = left_direction == right_direction
        adjacency[left].append((right, must_flip))
        adjacency[right].append((left, must_flip))
    return adjacency


def _face_flip_plan(
    adjacency: list[list[tuple[int, bool]]],
) -> tuple[list[int], tuple[tuple[int, ...], ...]]:
    """Find consistent local flips and the connected components they form.

    Args:
        adjacency: Face neighbors and the required relative winding for each edge.

    Returns:
        Per-face flip states and face indices grouped by connected component.

    Raises:
        ValueError: If the adjacent-face constraints are not orientable.
    """
    flip_state = [-1] * len(adjacency)
    components: list[list[int]] = []
    for start in range(len(adjacency)):
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
    return flip_state, tuple(tuple(component) for component in components)


def _corrected_face_winding(
    triangles: tuple[tuple[int, int, int], ...],
    flip_state: list[int],
) -> tuple[tuple[int, int, int], ...]:
    """Apply the computed local flips while preserving face order.

    Args:
        triangles: Original triangle vertex indices.
        flip_state: Per-face flags returned by the adjacency traversal.

    Returns:
        Triangles with coherent winding in their original face order.
    """
    corrected = [list(face) for face in triangles]
    for face_index, should_flip in enumerate(flip_state):
        if should_flip:
            corrected[face_index][1], corrected[face_index][2] = (
                corrected[face_index][2],
                corrected[face_index][1],
            )
    return tuple((int(face[0]), int(face[1]), int(face[2])) for face in corrected)


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

    Args:
        triangles: Ordered indexed faces that should form a closed manifold.

    Returns:
        Corrected triangle winding and face indices grouped by component.

    Raises:
        ValueError: If the mesh has boundary/non-manifold edges or is not orientable.
    """
    edge_owners = _edge_owners(triangles)
    adjacency = _face_adjacency(edge_owners, len(triangles))
    flip_state, components = _face_flip_plan(adjacency)
    return _corrected_face_winding(triangles, flip_state), components


def orient_closed_triangle_winding(
    vertices: Sequence[Sequence[float]],
    triangles: Sequence[Sequence[int]],
) -> tuple[tuple[int, int, int], ...]:
    """Return closed manifold triangles with consistent, outward face winding.

    Vertex and face indices remain stable. An adjacent-face walk fixes local flips
    from source assets, then signed volume selects the outward orientation per
    connected component. Open, non-manifold, degenerate, or non-orientable inputs
    are rejected rather than silently weakening collision-surface validation.

    Args:
        vertices: Ordered 3D vertex coordinates used to calculate component volumes.
        triangles: Ordered triangle vertex indices forming a closed mesh.

    Returns:
        tuple[tuple[int, int, int], ...]: Face winding with consistent outward normals.

    Raises:
        ValueError: If coordinates or triangle indices are invalid, or a component has
            no reliable enclosed volume.
    """
    points = np.asarray(vertices, dtype=np.float64)
    faces = np.asarray(triangles, dtype=np.int64)
    if points.ndim != 2 or points.shape[1] != _COORDINATE_DIMENSIONS or not len(points):
        msg = "closed mesh vertices must have shape (N, 3)"
        raise ValueError(msg)
    if faces.ndim != 2 or faces.shape[1] != _TRIANGLE_VERTEX_COUNT or not len(faces):
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
