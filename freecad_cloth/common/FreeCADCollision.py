# Copyright (C) 2026 FreeCAD Cloth contributors
"""FreeCAD-to-neutral collision-surface adapter."""

from freecad_cloth.common.ValidationModels import validate_finite_number
from freecad_cloth.shared.collision import CollisionSurface
from freecad_cloth.shared.mesh_topology import orient_closed_triangle_winding


def surface_from_freecad(
    obj: object, deflection: float = 1.0, thickness: float = 0.0
) -> CollisionSurface:
    """Convert a FreeCAD mesh or shape into a deterministic collision surface."""
    deflection = validate_finite_number(deflection)
    thickness = validate_finite_number(thickness)
    if deflection <= 0.0:
        raise ValueError("deflection must be positive and finite")
    mesh = getattr(obj, "Mesh", None)
    topology = getattr(mesh, "Topology", None) if mesh is not None else None
    shape = getattr(obj, "Shape", None)
    if topology is not None:
        try:
            raw_vertices, raw_faces = topology
            points = tuple((float(v.x), float(v.y), float(v.z)) for v in raw_vertices)
            triangles = tuple(tuple(i for i in face) for face in raw_faces)
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError("FreeCAD object has unusable Mesh topology") from exc
    elif shape is not None and not shape.isNull():
        vertices, faces = shape.tessellate(float(deflection))
        points = tuple((float(v.x), float(v.y), float(v.z)) for v in vertices)
        triangles = tuple(tuple(i for i in face) for face in faces)
    else:
        raise TypeError("expected a FreeCAD shape or mesh object")
    # FreeCAD may expose locally inconsistent facet winding after adapting a
    # closed authored mesh into its native Mesh.Topology representation. Repair
    # closed surfaces by index only; leave intentionally open targets untouched.
    try:
        triangles = orient_closed_triangle_winding(points, triangles)
    except ValueError as exc:
        if str(getattr(obj, "AvatarType", "")) == "ClothAvatar":
            try:
                import FreeCAD as App

                App.Console.PrintWarning(
                    "avatar collision winding normalization skipped reason=%s\n" % exc
                )
            except ImportError:
                pass
    return CollisionSurface(
        points, triangles, getattr(obj, "Label", "body") or "body", thickness
    ).validate()
