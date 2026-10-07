"""FreeCAD-to-neutral collision-surface adapter."""

from freecad_cloth.shared.collision import CollisionSurface


def surface_from_freecad(obj, deflection: float = 1.0, thickness: float = 0.0) -> CollisionSurface:
    """Convert a FreeCAD mesh or shape into a deterministic collision surface."""
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
    return CollisionSurface(
        points, triangles, getattr(obj, "Label", "body") or "body", float(thickness)
    ).validate()



def decimate_collision_surface(
    surface: CollisionSurface, target_triangles: int
) -> CollisionSurface:
    """Derive a PBD collision mesh with FreeCAD's native mesh simplifier."""
    target = int(target_triangles)
    surface.validate()
    if target < 0:
        raise ValueError("target_triangles must be >= 0")
    if target == 0 or len(surface.triangles) <= target:
        return surface

    import Mesh

    facets = [
        surface.vertices[index]
        for triangle in surface.triangles
        for index in triangle
    ]
    simplified = Mesh.Mesh(facets)
    simplified.decimate(target)
    vertices, triangles = simplified.Topology
    result = CollisionSurface(
        tuple((float(vertex.x), float(vertex.y), float(vertex.z)) for vertex in vertices),
        tuple(tuple(int(index) for index in triangle) for triangle in triangles),
        surface.region,
        surface.thickness,
    )
    return result.validate()
