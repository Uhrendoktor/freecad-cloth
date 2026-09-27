"""Solver-independent avatar and collision-surface contract.

The model layer deliberately does not import FreeCAD.  ``surface_from_freecad``
is the small GUI/runtime bridge used by the document workbench.
"""
from dataclasses import dataclass
from typing import Tuple


def _farthest_point_indices(centroids, limit):
    """Select deterministic spatial representatives using normalized Farthest Point Sampling.

    Centroids are normalized independently along each non-degenerate axis so an
    anisotropic humanoid does not spend most of the collision budget on its
    longest axis. NumPy is already present in the FreeCAD runtime; a small pure
    Python fallback keeps the model-layer helper usable without a new dependency.
    """
    count = len(centroids)
    if limit >= count:
        return list(range(count))
    if limit <= 0:
        return []

    mins = [min(point[axis] for point in centroids) for axis in range(3)]
    maxs = [max(point[axis] for point in centroids) for axis in range(3)]
    spans = [maxs[axis] - mins[axis] for axis in range(3)]

    try:
        import numpy as np
    except ImportError:
        normalized = [
            tuple(
                0.0 if spans[axis] <= 1e-12 else (point[axis] - mins[axis]) / spans[axis]
                for axis in range(3)
            )
            for point in centroids
        ]
        selected = [min(range(count), key=lambda i: normalized[i])]
        nearest = [
            sum((normalized[index][axis] - normalized[selected[0]][axis]) ** 2 for axis in range(3))
            for index in range(count)
        ]
        while len(selected) < limit:
            next_index = max(range(count), key=nearest.__getitem__)
            selected.append(next_index)
            reference = normalized[next_index]
            for index, point in enumerate(normalized):
                distance = sum((point[axis] - reference[axis]) ** 2 for axis in range(3))
                if distance < nearest[index]:
                    nearest[index] = distance
        return selected

    points = np.asarray(centroids, dtype=float)
    scale = np.asarray([span if span > 1e-12 else 1.0 for span in spans], dtype=float)
    normalized = (points - np.asarray(mins, dtype=float)) / scale
    selected = [int(np.argmin(np.sum(normalized * normalized, axis=1)))]
    nearest = np.sum((normalized - normalized[selected[0]]) ** 2, axis=1)
    for _ in range(1, limit):
        next_index = int(np.argmax(nearest))
        selected.append(next_index)
        distances = np.sum((normalized - normalized[next_index]) ** 2, axis=1)
        nearest = np.minimum(nearest, distances)
    return selected


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

    indices = _farthest_point_indices(centroids, limit)
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
