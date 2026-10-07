"""Neutral solver-facing collision-surface value objects."""

from dataclasses import dataclass

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


def surface_from_triangles(vertices, triangles, region="body", thickness=0.0) -> CollisionSurface:
    """Build and validate a collision surface without a host dependency."""
    return CollisionSurface(
        tuple(tuple(float(c) for c in vertex) for vertex in vertices),
        tuple(tuple(int(i) for i in triangle) for triangle in triangles),
        str(region),
        float(thickness),
    ).validate()
