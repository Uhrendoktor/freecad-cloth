"""FreeCAD/OCCT geometry adapter for seam allowances.

This module is deliberately isolated from PatternModel so the headless semantic
layer remains independent of FreeCAD.
"""


def _make_offset_wire(wire, distance, join_type=0):
    """Offset an existing FreeCAD wire across supported Part APIs."""
    if distance < 0:
        raise ValueError("offset distance must be non-negative")
    if not hasattr(wire, "makeOffset2D"):
        raise RuntimeError("installed FreeCAD Part API does not expose Wire.makeOffset2D")
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
    return _make_offset_wire(wire, distance, join_type)


def native_offset_wire(wire, distance, join_type=0):
    """Compatibility API for callers that already own a FreeCAD wire."""
    return _make_offset_wire(wire, distance, join_type)


def compare_native_offset(piece, distance):
    """Generate a native offset candidate while preserving the semantic source."""
    piece.validate()
    return offset_outline(piece.outline, distance)
