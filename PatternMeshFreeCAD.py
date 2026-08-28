"""FreeCAD MeshPart adapter preserving the semantic TriangleMesh contract."""


def mesh_shape_from_outline(outline, linear_deflection=1.0, angular_deflection=0.5):
    """Generate a native FreeCAD mesh from a planar pattern outline.

    Boundary provenance remains represented by the original semantic outline;
    native mesh face ordering must never be treated as stable sewing IDs.
    """
    if len(outline) < 3:
        raise ValueError("outline needs at least three points")
    try:
        import FreeCAD as App
        import Part
        import MeshPart
    except ImportError as exc:
        raise RuntimeError("FreeCAD Part/MeshPart is required") from exc
    points = [App.Vector(float(x), float(y), 0.0) for x, y in outline]
    points.append(points[0])
    wire = Part.makePolygon(points)
    face = Part.Face(wire)
    return MeshPart.meshFromShape(Shape=face, LinearDeflection=float(linear_deflection), AngularDeflection=float(angular_deflection), Relative=False)


def boundary_provenance(outline):
    """Return stable semantic boundary IDs independent of MeshPart face order."""
    return tuple((i, f"edge:{i}") for i in range(len(outline)))
