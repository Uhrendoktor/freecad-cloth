"""Helpers for keeping authored avatar meshes compact and consistently oriented."""

from collections.abc import Sequence


def compact_mesh(vertices, triangles):
    """Provide the public compact mesh operation."""
    used = sorted({int(i) for tri in triangles for i in tri})
    remap = {old: new for new, old in enumerate(used)}
    compact_vertices = tuple(vertices[i] for i in used)
    compact_triangles = tuple(tuple(remap[int(i)] for i in tri) for tri in triangles)
    return compact_vertices, compact_triangles


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
    import numpy as np

    points = np.asarray(vertices, dtype=np.float64)
    faces = np.asarray(triangles, dtype=np.int64)
    if points.ndim != 2 or points.shape[1] != 3 or not len(points):
        raise ValueError("closed mesh vertices must have shape (N, 3)")
    if faces.ndim != 2 or faces.shape[1] != 3 or not len(faces):
        raise ValueError("closed mesh triangles must have shape (M, 3)")
    if not bool(np.isfinite(points).all()):
        raise ValueError("closed mesh vertices must be finite")
    if bool(np.any(faces < 0) or np.any(faces >= len(points))):
        raise ValueError("closed mesh triangle index is outside the vertex array")

    edge_owners: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for face_index, (a, b, c) in enumerate(faces.tolist()):
        for first, second in ((a, b), (b, c), (c, a)):
            if first == second:
                raise ValueError("closed mesh contains a degenerate indexed edge")
            edge = (min(first, second), max(first, second))
            direction = 1 if first < second else -1
            edge_owners.setdefault(edge, []).append((face_index, direction))

    if any(len(owners) != 2 for owners in edge_owners.values()):
        raise ValueError("closed mesh requires every undirected edge to appear exactly twice")

    adjacency: list[list[tuple[int, bool]]] = [[] for _ in range(len(faces))]
    for owners in edge_owners.values():
        (left, left_direction), (right, right_direction) = owners
        must_flip = left_direction == right_direction
        adjacency[left].append((right, must_flip))
        adjacency[right].append((left, must_flip))

    # -1 means unvisited; zero/one records the required local face flip.
    flip_state = [-1] * len(faces)
    components: list[list[int]] = []
    for start in range(len(faces)):
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
                    raise ValueError("closed mesh triangle winding is not orientable")
        components.append(component)

    corrected = faces.copy()
    flipped = np.flatnonzero(np.asarray(flip_state, dtype=np.bool_))
    if len(flipped):
        second = corrected[flipped, 1].copy()
        corrected[flipped, 1] = corrected[flipped, 2]
        corrected[flipped, 2] = second

    for component in components:
        component_faces = corrected[np.asarray(component, dtype=np.int64)]
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
            raise ValueError("closed mesh component has no reliable enclosed volume")
        if signed_volume6 < 0.0:
            component_indices = np.asarray(component, dtype=np.int64)
            second = corrected[component_indices, 1].copy()
            corrected[component_indices, 1] = corrected[component_indices, 2]
            corrected[component_indices, 2] = second

    return tuple(tuple(int(index) for index in face) for face in corrected.tolist())
