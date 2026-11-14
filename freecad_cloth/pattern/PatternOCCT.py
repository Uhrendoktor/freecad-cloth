# Copyright (C) 2026 FreeCAD Cloth contributors
"""FreeCAD/OCCT geometry adapter for seam allowances.

This module is deliberately isolated from PatternModel so the headless semantic
layer remains independent of FreeCAD.
"""


def _make_offset_wire(wire, distance, join_type=0):
    """Offset an existing FreeCAD wire across supported Part APIs."""
    if distance < 0:
        msg = "offset distance must be non-negative"
        raise ValueError(msg)
    if not hasattr(wire, "makeOffset2D"):
        msg = "installed FreeCAD Part API does not expose Wire.makeOffset2D"
        raise RuntimeError(msg)
    try:
        return wire.makeOffset2D(float(distance), int(join_type), False, False, True)
    except TypeError:
        # Older FreeCAD releases expose fewer positional parameters.
        return wire.makeOffset2D(float(distance), int(join_type))


def offset_outline(outline, distance, join_type=0):
    """Return an OCCT-generated offset wire/shape for a 2D outline.

    The caller owns semantic edge IDs; OCCT-generated edges are therefore
    treated as derived geometry and never used as stable sewing identifiers.

    Args:
        outline: Ordered planar boundary coordinates used to build the source wire.
        distance: Non-negative offset distance in model units.
        join_type: Native OCCT join-style selector passed to FreeCAD Part.

    Returns:
        Native offset wire or compound shape returned by the installed Part API.

    Raises:
        ValueError: If the outline has too few points or the offset distance is negative.
        RuntimeError: If the FreeCAD Part/OCCT module is unavailable.
    """
    try:
        import FreeCAD as App
        import Part
    except ImportError as exc:
        msg = "FreeCAD Part/OCCT is required for native offset geometry"
        raise RuntimeError(msg) from exc
    if len(outline) < 3:
        msg = "outline needs at least three points"
        raise ValueError(msg)
    points = [App.Vector(float(x), float(y), 0.0) for x, y in outline]
    points.append(points[0])
    wire = Part.makePolygon(points)
    return _make_offset_wire(wire, distance, join_type)


def native_offset_wire(wire, distance, join_type=0):
    """Offset a caller-owned FreeCAD wire without rebuilding its source outline.

    Args:
        wire: Native FreeCAD wire to offset.
        distance: Non-negative offset distance in model units.
        join_type: Native OCCT join-style selector passed to FreeCAD Part.

    Returns:
        Native offset wire or shape produced by the installed Part API.

    Raises:
        ValueError: If the offset distance is negative.
        RuntimeError: If the installed Part API does not expose wire offset support.
    """
    return _make_offset_wire(wire, distance, join_type)


def compare_native_offset(piece, distance):
    """Generate a native offset candidate while preserving the semantic source.

    Args:
        piece: Validated semantic pattern piece that supplies the source outline.
        distance: Non-negative offset distance in model units.

    Returns:
        Native offset geometry derived from the validated piece outline.

    Raises:
        ValueError: If the source piece or offset distance is invalid.
        RuntimeError: If the FreeCAD Part/OCCT module is unavailable.
    """
    piece.validate()
    return offset_outline(piece.outline, distance)
