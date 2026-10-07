"""Neutral solver-facing collision-surface value objects."""

import heapq
from dataclasses import dataclass
from math import ceil


@dataclass(frozen=True)
class CollisionSurface:
    """Immutable triangle surface consumed by collision-aware runtimes."""

    vertices: tuple[tuple[float, float, float], ...]
    triangles: tuple[tuple[int, int, int], ...]
    region: str = "body"
    thickness: float = 0.0

    def validate(self) -> "CollisionSurface":
        """Validate the immutable collision surface and return it."""
        count = len(self.vertices)
        if count < 3 or not self.triangles:
            raise ValueError("collision surface needs vertices and triangles")
        if self.thickness < 0:
            raise ValueError("collision thickness must not be negative")
        for triangle in self.triangles:
            if len(triangle) != 3 or any(i < 0 or i >= count for i in triangle):
                raise ValueError("collision triangle index out of range")
        if not self.region.strip():
            raise ValueError("collision region must not be empty")
        return self

    @property
    def center(self) -> tuple[float, float, float]:
        """Return the arithmetic center of the surface vertices."""
        count = len(self.vertices)
        if not count:
            return (0.0, 0.0, 0.0)
        return tuple(sum(vertex[i] for vertex in self.vertices) / count for i in range(3))

    def with_thickness(self, thickness: float) -> "CollisionSurface":
        """Return the same surface with a different collision thickness."""
        return CollisionSurface(
            self.vertices, self.triangles, self.region, float(thickness)
        ).validate()


def _is_closed_triangle_surface(triangles):
    """Return whether every undirected triangle edge has exactly two incident faces."""
    edge_counts = {}
    for triangle in triangles:
        a, b, c = (int(index) for index in triangle)
        for left, right in ((a, b), (b, c), (c, a)):
            edge = (min(left, right), max(left, right))
            edge_counts[edge] = edge_counts.get(edge, 0) + 1
    return bool(edge_counts) and all(count == 2 for count in edge_counts.values())


def _decimate_closed_triangles(vertices, triangles, target_count):
    """Reduce a closed triangle manifold by legal shortest-edge collapses."""
    target = int(target_count)
    points = [list(vertex) for vertex in vertices]
    faces = [tuple(int(index) for index in triangle) for triangle in triangles]
    alive = [True] * len(faces)
    vertex_faces = [set() for _ in points]
    vertex_neighbors = [set() for _ in points]
    edge_faces = {}
    triangle_keys = set()

    for face_index, triangle in enumerate(faces):
        vertex_faces[triangle[0]].add(face_index)
        vertex_faces[triangle[1]].add(face_index)
        vertex_faces[triangle[2]].add(face_index)
        triangle_keys.add(tuple(sorted(triangle)))
        for left, right in (
            (triangle[0], triangle[1]),
            (triangle[1], triangle[2]),
            (triangle[2], triangle[0]),
        ):
            edge = (min(left, right), max(left, right))
            edge_faces.setdefault(edge, set()).add(face_index)
            vertex_neighbors[left].add(right)
            vertex_neighbors[right].add(left)

    versions = [0] * len(points)
    heap = []

    def push_edge(left, right):
        if left == right or not vertex_faces[left] or not vertex_faces[right]:
            return
        distance = sum(
            (points[left][axis] - points[right][axis]) ** 2 for axis in range(3)
        )
        heapq.heappush(heap, (distance, left, right, versions[left], versions[right]))

    for left, right in edge_faces:
        push_edge(left, right)

    alive_faces = len(faces)
    while alive_faces > target and heap:
        _distance, left, right, left_version, right_version = heapq.heappop(heap)
        if (
            versions[left] != left_version
            or versions[right] != right_version
            or not vertex_faces[left]
            or not vertex_faces[right]
            or right not in vertex_neighbors[left]
        ):
            continue

        edge = (min(left, right), max(left, right))
        incident = edge_faces.get(edge, set())
        if len(incident) != 2:
            continue

        opposite = {
            next(index for index in faces[face_index] if index not in (left, right))
            for face_index in incident
        }
        if vertex_neighbors[left] & vertex_neighbors[right] != opposite:
            continue

        affected = vertex_faces[left] | vertex_faces[right]
        replacements = []
        replacement_keys = set()
        degenerate = 0
        invalid = False
        for face_index in affected:
            if not alive[face_index]:
                continue
            original = faces[face_index]
            replacement = tuple(left if index == right else index for index in original)
            if len(set(replacement)) < 3:
                degenerate += 1
                continue
            key = tuple(sorted(replacement))
            if key in replacement_keys or (
                key in triangle_keys and tuple(sorted(original)) != key
            ):
                invalid = True
                break
            replacement_keys.add(key)
            replacements.append((face_index, replacement))
        if invalid or degenerate != 2:
            continue

        for face_index in affected:
            if not alive[face_index]:
                continue
            original = faces[face_index]
            alive[face_index] = False
            alive_faces -= 1
            triangle_keys.discard(tuple(sorted(original)))
            for index in original:
                vertex_faces[index].discard(face_index)
            for a, b in (
                (original[0], original[1]),
                (original[1], original[2]),
                (original[2], original[0]),
            ):
                edge_key = (min(a, b), max(a, b))
                edge_set = edge_faces.get(edge_key)
                if edge_set is not None:
                    edge_set.discard(face_index)
                    if not edge_set:
                        edge_faces.pop(edge_key, None)
                        vertex_neighbors[a].discard(b)
                        vertex_neighbors[b].discard(a)

        points[left] = [
            (points[left][axis] + points[right][axis]) * 0.5 for axis in range(3)
        ]
        versions[left] += 1
        versions[right] += 1
        vertex_faces[right].clear()
        vertex_neighbors[right].clear()

        for face_index, replacement in replacements:
            faces[face_index] = replacement
            alive[face_index] = True
            alive_faces += 1
            triangle_keys.add(tuple(sorted(replacement)))
            for index in replacement:
                vertex_faces[index].add(face_index)
            for a, b in (
                (replacement[0], replacement[1]),
                (replacement[1], replacement[2]),
                (replacement[2], replacement[0]),
            ):
                edge_key = (min(a, b), max(a, b))
                edge_faces.setdefault(edge_key, set()).add(face_index)
                vertex_neighbors[a].add(b)
                vertex_neighbors[b].add(a)

        for neighbor in tuple(vertex_neighbors[left]):
            push_edge(left, neighbor)

    reduced = [faces[index] for index, is_alive in enumerate(alive) if is_alive]
    if len(reduced) > target or not _is_closed_triangle_surface(reduced):
        return None

    used = sorted({index for triangle in reduced for index in triangle})
    remap = {old: new for new, old in enumerate(used)}
    reduced_vertices = tuple(tuple(points[index]) for index in used)
    reduced_triangles = tuple(
        tuple(remap[index] for index in triangle) for triangle in reduced
    )
    return reduced_vertices, reduced_triangles


def coarsen_collision_surface(
    surface: CollisionSurface, max_triangles: int = 1024
) -> CollisionSurface:
    """Reduce within a triangle budget without opening closed collision shells."""
    limit = int(max_triangles)
    surface.validate()
    if limit < 1:
        raise ValueError("max_triangles must be positive")
    if len(surface.triangles) <= limit:
        return surface

    if _is_closed_triangle_surface(surface.triangles):
        if limit < 4:
            return surface
        reduced = _decimate_closed_triangles(surface.vertices, surface.triangles, limit)
        if reduced is not None:
            vertices, triangles = reduced
            return CollisionSurface(
                vertices, triangles, surface.region, surface.thickness
            ).validate()
        return surface

    return _coarsen_open_surface(surface, limit)


def _coarsen_open_surface(surface: CollisionSurface, limit: int) -> CollisionSurface:
    """Reduce an open collision surface spatially; closed shells never use this path."""
    points = surface.vertices
    centroids = []
    mins = [float("inf")] * 3
    maxs = [float("-inf")] * 3
    for ia, ib, ic in surface.triangles:
        a, b, c = points[ia], points[ib], points[ic]
        center = tuple((a[i] + b[i] + c[i]) / 3.0 for i in range(3))
        centroids.append(center)
        for i in range(3):
            mins[i] = min(mins[i], center[i])
            maxs[i] = max(maxs[i], center[i])

    span = max(maxs[i] - mins[i] for i in range(3))
    if span <= 1e-9:
        step = 1
        cell = 1.0
    else:
        step = max(1, int(ceil(limit ** (1.0 / 3.0))))
        cell = span / step

    selected = {}
    for index, center in enumerate(centroids):
        if span <= 1e-9:
            key = (0, 0, 0)
        else:
            key = tuple(
                min(step - 1, max(0, int((center[i] - mins[i]) / cell))) for i in range(3)
            )
        selected.setdefault(key, index)

    indices = list(selected.values())
    if len(indices) > limit:
        stride = max(1, int(ceil(len(indices) / float(limit))))
        indices = indices[::stride][:limit]
    elif len(indices) < limit:
        used = set(indices)
        stride = max(1, len(surface.triangles) // limit)
        for index in range(0, len(surface.triangles), stride):
            if index not in used:
                indices.append(index)
                used.add(index)
                if len(indices) >= limit:
                    break

    return CollisionSurface(
        surface.vertices,
        tuple(surface.triangles[index] for index in indices[:limit]),
        surface.region,
        surface.thickness,
    ).validate()


def surface_from_triangles(vertices, triangles, region="body", thickness=0.0) -> CollisionSurface:
    """Build and validate a collision surface without a host dependency."""
    return CollisionSurface(
        tuple(tuple(float(c) for c in vertex) for vertex in vertices),
        tuple(tuple(int(i) for i in triangle) for triangle in triangles),
        str(region),
        float(thickness),
    ).validate()
