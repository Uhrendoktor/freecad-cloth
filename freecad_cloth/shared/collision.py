"""Neutral solver-facing collision-surface value objects."""

from collections.abc import Iterable
from dataclasses import dataclass
from numbers import Real

from freecad_cloth.common.ValidationModels import CollisionSurfaceInput

@dataclass(frozen=True)
class CollisionSurface:
    """Immutable triangle surface consumed by collision-aware runtimes."""

    vertices: tuple[tuple[float, float, float], ...]
    triangles: tuple[tuple[int, int, int], ...]
    region: str = "body"
    thickness: float = 0.0

    def validate(self) -> "CollisionSurface":
        """Validate the immutable collision surface and return it."""
        CollisionSurfaceInput.model_validate(
            {
                "vertices": self.vertices,
                "triangles": self.triangles,
                "region": self.region,
                "thickness": self.thickness,
            }
        )
        return self

    @property
    def center(self) -> tuple[float, float, float]:
        """Return the arithmetic center of the surface vertices."""
        count = len(self.vertices)
        if not count:
            return (0.0, 0.0, 0.0)
        return (
            sum(vertex[0] for vertex in self.vertices) / count,
            sum(vertex[1] for vertex in self.vertices) / count,
            sum(vertex[2] for vertex in self.vertices) / count,
        )

    def with_thickness(self, thickness: float) -> "CollisionSurface":
        """Return the same surface with a different collision thickness."""
        return CollisionSurface(
            self.vertices, self.triangles, self.region, float(thickness)
        ).validate()


def surface_from_triangles(
    vertices: Iterable[Iterable[Real]],
    triangles: Iterable[Iterable[int]],
    region: str = "body",
    thickness: float = 0.0,
) -> CollisionSurface:
    """Build and validate a collision surface without a host dependency."""
    validated = CollisionSurfaceInput.model_validate(
        {
            "vertices": vertices,
            "triangles": triangles,
            "region": region,
            "thickness": thickness,
        }
    )
    return CollisionSurface(
        validated.vertices,
        validated.triangles,
        validated.region,
        validated.thickness,
    )
