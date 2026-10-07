"""Neutral solver-facing collision-surface value objects."""

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


def coarsen_collision_surface(
    surface: CollisionSurface, max_triangles: int = 1024
) -> CollisionSurface:
    """Derive a spatially covered collision surface within a triangle budget."""
    limit = int(max_triangles)
    surface.validate()
    if limit < 1:
        raise ValueError("max_triangles must be positive")
    if len(surface.triangles) <= limit:
        return surface
    if _is_closed_triangle_surface(surface.triangles):
        return surface

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
