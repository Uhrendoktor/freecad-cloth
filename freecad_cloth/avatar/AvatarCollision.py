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
    """Derive a deterministically covered collision surface from a real authored mesh.

    The visible avatar remains the full authored mesh. The solver gets at most
    ``max_triangles`` source triangles selected by normalized farthest-point
    sampling of triangle centroids. Normalizing each axis prevents a tall avatar
    from starving lateral coverage, while source vertices, winding, region and
    thickness remain unchanged. No proxy geometry is created.
    """
    limit = int(max_triangles)
    surface.validate()
    if limit < 1:
        raise ValueError("max_triangles must be positive")
    triangle_count = len(surface.triangles)
    if triangle_count <= limit:
        return surface

    centroids = []
    for ia, ib, ic in surface.triangles:
        a, b, c = surface.vertices[ia], surface.vertices[ib], surface.vertices[ic]
        centroids.append((
            (a[0] + b[0] + c[0]) / 3.0,
            (a[1] + b[1] + c[1]) / 3.0,
            (a[2] + b[2] + c[2]) / 3.0,
        ))

    import numpy as np

    points = np.asarray(centroids, dtype=float)
    mins = points.min(axis=0)
    spans = points.max(axis=0) - mins
    safe_spans = np.where(spans > 1e-12, spans, 1.0)
    normalized = (points - mins) / safe_spans

    selected = np.empty(limit, dtype=np.int64)
    center = np.full(3, 0.5, dtype=float)
    first = int(np.argmin(np.sum((normalized - center) ** 2, axis=1)))
    selected[0] = first

    nearest_distance_sq = np.sum((normalized - normalized[first]) ** 2, axis=1)
    nearest_distance_sq[first] = -1.0

    for slot in range(1, limit):
        next_index = int(np.argmax(nearest_distance_sq))
        selected[slot] = next_index
        delta = normalized - normalized[next_index]
        distance_sq = np.sum(delta * delta, axis=1)
        nearest_distance_sq = np.minimum(nearest_distance_sq, distance_sq)
        nearest_distance_sq[next_index] = -1.0

    selected_indices = tuple(int(index) for index in selected)
    if len(set(selected_indices)) != limit:
        raise RuntimeError("collision coarsening selected duplicate triangle indices")

    triangles = tuple(surface.triangles[index] for index in selected_indices)
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
