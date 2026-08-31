"""Solver-independent avatar and collision-surface contract.

The model layer deliberately does not import FreeCAD.  ``surface_from_freecad``
is the small GUI/runtime bridge used by the document workbench.
"""
from dataclasses import dataclass
from math import sqrt
from typing import Tuple


@dataclass(frozen=True)
class CollisionSurface:
    vertices: Tuple[Tuple[float, float, float], ...]
    triangles: Tuple[Tuple[int, int, int], ...]
    region: str = "body"
    thickness: float = 0.0

    def validate(self) -> None:
        n = len(self.vertices)
        if n < 3 or not self.triangles:
            raise ValueError("collision surface needs vertices and triangles")
        if self.thickness < 0:
            raise ValueError("collision thickness must not be negative")
        for tri in self.triangles:
            if len(tri) != 3 or any(i < 0 or i >= n for i in tri):
                raise ValueError("collision triangle index out of range")
        if not self.region.strip():
            raise ValueError("collision region must not be empty")

    @property
    def center(self) -> Tuple[float, float, float]:
        n = len(self.vertices)
        if not n:
            return (0.0, 0.0, 0.0)
        return tuple(sum(v[i] for v in self.vertices) / n for i in range(3))

    def with_thickness(self, thickness: float) -> "CollisionSurface":
        result = CollisionSurface(self.vertices, self.triangles, self.region, float(thickness))
        result.validate()
        return result


@dataclass(frozen=True)
class AvatarSpec:
    name: str
    unit: str = "mm"
    coordinate_system: str = "RH-Z-up"
    collision: CollisionSurface | None = None

    def validate(self) -> None:
        if not self.name.strip() or self.unit not in {"mm", "cm", "m"}:
            raise ValueError("invalid avatar identity or units")
        if self.coordinate_system != "RH-Z-up":
            raise ValueError("unsupported coordinate convention")
        if self.collision:
            self.collision.validate()


def surface_from_freecad(obj, deflection: float = 1.0, thickness: float = 0.0) -> CollisionSurface:
    """Convert a FreeCAD shape/mesh object into a deterministic triangle surface.

    The import is intentionally lazy so headless model tests never require a
    FreeCAD installation.  Part shapes use OCC tessellation; Mesh::Feature
    objects are consumed through their mesh topology when no Shape is exposed.
    """
    if deflection <= 0:
        raise ValueError("deflection must be positive")
    if hasattr(obj, "Shape") and not obj.Shape.isNull():
        vertices, faces = obj.Shape.tessellate(float(deflection))
        points = tuple((float(v.x), float(v.y), float(v.z)) for v in vertices)
        triangles = tuple(tuple(int(i) for i in face) for face in faces)
    elif hasattr(obj, "Mesh"):
        topology = getattr(obj.Mesh, "Topology", None)
        if topology is None:
            raise ValueError("FreeCAD object has no usable Shape or Mesh topology")
        raw_vertices, raw_faces = topology
        points = tuple((float(v.x), float(v.y), float(v.z)) for v in raw_vertices)
        triangles = tuple(tuple(int(i) for i in face) for face in raw_faces)
    else:
        raise TypeError("expected a FreeCAD shape or mesh object")
    surface = CollisionSurface(points, triangles, getattr(obj, "Label", "body") or "body", float(thickness))
    surface.validate()
    return surface


def surface_from_triangles(vertices, triangles, region="body", thickness=0.0) -> CollisionSurface:
    """Build and validate a solver-facing surface without importing FreeCAD."""
    surface = CollisionSurface(
        tuple(tuple(float(c) for c in v) for v in vertices),
        tuple(tuple(int(i) for i in tri) for tri in triangles),
        str(region),
        float(thickness),
    )
    surface.validate()
    return surface
