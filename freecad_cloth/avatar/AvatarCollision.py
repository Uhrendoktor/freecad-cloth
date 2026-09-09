"""Solver-independent avatar and collision-surface contract.

The model layer deliberately does not import FreeCAD.  ``surface_from_freecad``
is the small GUI/runtime bridge used by the document workbench.
"""
from dataclasses import dataclass
from math import ceil
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


def coarsen_collision_surface(surface: CollisionSurface, max_triangles: int = 1024) -> CollisionSurface:
    """Derive a spatially covered collision surface from a real authored mesh.

    The visible avatar remains the full MakeHuman mesh. The solver does not need
    every render triangle, so this keeps one representative triangle per coarse
    spatial cell until the requested triangle budget is reached. No proxy object
    is created and the result remains derived solely from the real avatar mesh.
    """
    limit = int(max_triangles)
    surface.validate()
    if limit < 1:
        raise ValueError("max_triangles must be positive")
    if len(surface.triangles) <= limit:
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
    else:
        cells_per_axis = max(1, int(ceil(limit ** (1.0 / 3.0))))
        cell = span / cells_per_axis
        step = max(1, cells_per_axis)

    selected = {}
    for index, center in enumerate(centroids):
        if span <= 1e-9:
            key = (0, 0, 0)
        else:
            key = tuple(min(step - 1, max(0, int((center[i] - mins[i]) / cell))) for i in range(3))
        if key not in selected:
            selected[key] = index

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

    triangles = tuple(surface.triangles[index] for index in indices[:limit])
    result = CollisionSurface(surface.vertices, triangles, surface.region, surface.thickness)
    result.validate()
    return result


def surface_from_freecad(obj, deflection: float = 1.0, thickness: float = 0.0) -> CollisionSurface:
    """Convert a FreeCAD shape/mesh object into a deterministic triangle surface.

    Mesh::Feature is consumed from its authored topology first. This avoids
    depending on transient OCC Shape generation for native mesh avatars and
    keeps the collision source identical to the visible mesh.
    """
    if deflection <= 0:
        raise ValueError("deflection must be positive")
    mesh = getattr(obj, "Mesh", None)
    topology = getattr(mesh, "Topology", None) if mesh is not None else None
    if topology is not None:
        try:
            raw_vertices, raw_faces = topology
            points = tuple((float(v.x), float(v.y), float(v.z)) for v in raw_vertices)
            triangles = tuple(tuple(int(i) for i in face) for face in raw_faces)
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError("FreeCAD object has unusable Mesh topology") from exc
    elif hasattr(obj, "Shape") and not obj.Shape.isNull():
        vertices, faces = obj.Shape.tessellate(float(deflection))
        points = tuple((float(v.x), float(v.y), float(v.z)) for v in vertices)
        triangles = tuple(tuple(int(i) for i in face) for face in faces)
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
