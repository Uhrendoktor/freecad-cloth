"""FreeCAD/OCCT geometry adapter for seam allowances.

This module is deliberately isolated from PatternModel so the headless semantic
layer remains independent of FreeCAD.
"""


def native_offset_wire(wire, distance, join_type=0):
    """Return a native OCCT 2D offset of an existing FreeCAD wire.

    The input wire is already FreeCAD/Part geometry, so this adapter does not
    rebuild the semantic outline or assign topology-derived sewing IDs. The
    caller owns semantic provenance; the returned topology is derived geometry.
    """
    if distance < 0:
        raise ValueError("offset distance must be non-negative")
    if wire is None or not hasattr(wire, "makeOffset2D"):
        raise TypeError("native_offset_wire expects a FreeCAD Part wire")
    try:
        return wire.makeOffset2D(float(distance), int(join_type), False, False, True)
    except TypeError:
        # Older FreeCAD releases expose fewer positional parameters.
        return wire.makeOffset2D(float(distance), int(join_type))


def offset_outline(outline, distance, join_type=0):
    """Return an OCCT-generated offset wire/shape for a 2D outline.

    The caller owns semantic edge IDs; OCCT-generated edges are therefore
    treated as derived geometry and never used as stable sewing identifiers.
    """
    if distance < 0:
        raise ValueError("offset distance must be non-negative")
    try:
        import FreeCAD as App
        import Part
    except ImportError as exc:
        raise RuntimeError("FreeCAD Part/OCCT is required for native offset geometry") from exc
    if len(outline) < 3:
        raise ValueError("outline needs at least three points")
    points = [App.Vector(float(x), float(y), 0.0) for x, y in outline]
    points.append(points[0])
    wire = Part.makePolygon(points)
    return native_offset_wire(wire, distance, join_type)


def compare_native_offset(piece, distance):
    """Generate a native offset candidate while preserving the semantic source."""
    piece.validate()
    return offset_outline(piece.outline, distance)
