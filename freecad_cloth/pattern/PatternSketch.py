# Copyright (C) 2026 FreeCAD Cloth contributors
"""FreeCAD-native Sketcher authoring adapter for Cloth Pattern pieces.

Sketcher is the editable geometry authority. PatternPiece stores semantic
identity and derived compatibility data; PatternIR preserves curve kind and
endpoint connectivity for downstream sewing and simulation adapters.
"""

from collections.abc import Sequence


def _piece_object(document, piece_id):
    return next(
        (obj for obj in document.Objects if getattr(obj, "PieceId", "") == str(piece_id)), None
    )


def _ensure_piece_properties(obj):
    if obj is None:
        return
    existing_sketch = getattr(obj, "Sketch", None)
    try:
        sketch_type = obj.getTypeIdOfProperty("Sketch")
    except (AttributeError, RuntimeError):
        sketch_type = ""
    if "Sketch" not in obj.PropertiesList or str(sketch_type) != "App::PropertyLinkGlobal":
        if "Sketch" in obj.PropertiesList:
            obj.removeProperty("Sketch")
        obj.addProperty("App::PropertyLinkGlobal", "Sketch", "Cloth")
        if existing_sketch is not None:
            obj.Sketch = existing_sketch
    if "GeometryAuthority" not in obj.PropertiesList:
        obj.addProperty("App::PropertyEnumeration", "GeometryAuthority", "Cloth")
        obj.GeometryAuthority = ["PatternParameters", "Sketcher"]


def _is_axis_aligned_rectangle(
    points: Sequence[tuple[float, float]], tolerance: float = 1e-7
) -> bool:
    """Return whether four points describe the four corners of an axis-aligned rectangle."""
    if len(points) != 4:
        return False
    xs = sorted({round(float(point[0]) / tolerance) for point in points})
    ys = sorted({round(float(point[1]) / tolerance) for point in points})
    if len(xs) != 2 or len(ys) != 2:
        return False
    corners = {
        (round(float(point[0]) / tolerance), round(float(point[1]) / tolerance)) for point in points
    }
    expected = {(x, y) for x in xs for y in ys}
    if corners != expected:
        return False
    return all(
        abs(float(a[0]) - float(b[0])) <= tolerance or abs(float(a[1]) - float(b[1])) <= tolerance
        for a, b in zip(points, (*points[1:], points[0]), strict=False)
    )


def _add_geometry(sketch, points):
    import FreeCAD as App
    import Part
    import Sketcher

    geometry = []
    for index, start in enumerate(points):
        end = points[(index + 1) % len(points)]
        geometry.append(
            Part.LineSegment(App.Vector(start[0], start[1], 0), App.Vector(end[0], end[1], 0))
        )
    sketch.addGeometry(geometry, False)

    # Coincident endpoint constraints keep the boundary topologically closed
    # while leaving dimensional degrees of freedom available to the user.
    constraints = [
        Sketcher.Constraint("Coincident", index, 2, (index + 1) % len(points), 1)
        for index in range(len(points))
    ]
    # Only infer a rectangle when its actual coordinates prove that intent.
    # Four arbitrary surface points must never be reshaped by assumed H/V constraints.
    if _is_axis_aligned_rectangle(points):
        constraints.extend(
            (
                Sketcher.Constraint("Horizontal", 0),
                Sketcher.Constraint("Vertical", 1),
                Sketcher.Constraint("Horizontal", 2),
                Sketcher.Constraint("Vertical", 3),
            )
        )
    sketch.addConstraint(constraints)


def _add_native_geometry(
    sketch: object, segments: Sequence[tuple[str, Sequence[tuple[float, float]]]]
) -> None:
    """Add connected line/B-spline boundary segments to a native Sketcher sketch."""
    import FreeCAD as App
    import Part
    import Sketcher

    geometry = []
    for kind, points in segments:
        vectors = [App.Vector(float(point[0]), float(point[1]), 0) for point in points]
        if kind == "line":
            if len(vectors) != 2:
                msg = "line boundary segment requires exactly two endpoints"
                raise ValueError(msg)
            geometry.append(Part.LineSegment(vectors[0], vectors[1]))
        elif kind == "bspline":
            if len(vectors) < 3:
                msg = "B-spline boundary segment requires an interior curve point"
                raise ValueError(msg)
            curve = Part.BSplineCurve()
            curve.interpolate(vectors)
            geometry.append(curve)
        else:
            msg = f"unsupported surface boundary segment type: {kind}"
            raise ValueError(msg)
    if len(geometry) < 3:
        msg = "surface sketch requires at least three connected boundary segments"
        raise ValueError(msg)
    sketch.addGeometry(geometry, False)
    constraints = [
        Sketcher.Constraint("Coincident", index, 2, (index + 1) % len(geometry), 1)
        for index in range(len(geometry))
    ]
    sketch.addConstraint(constraints)


def create_sketch_for_piece(
    piece,
    document=None,
    geometry_segments: Sequence[tuple[str, Sequence[tuple[float, float]]]] | None = None,
):
    """Create or return the native Sketcher representation for ``piece``."""
    try:
        import FreeCAD as App
    except ImportError as exc:
        msg = "FreeCAD Sketcher is required for PatternSketch"
        raise RuntimeError(msg) from exc

    document = document or App.ActiveDocument
    if document is None:
        document = App.newDocument("ClothPattern")
    piece.validate()

    existing = next(
        (
            obj
            for obj in document.Objects
            if getattr(obj, "PatternPieceId", "") == str(piece.id)
            and getattr(obj, "TypeId", "") == "Sketcher::SketchObject"
        ),
        None,
    )
    if existing is not None:
        if geometry_segments is not None:
            existing.clear()
            _add_native_geometry(existing, geometry_segments)
            existing.SemanticEdgeIds = [
                f"{piece.id}:edge:{i}" for i in range(len(geometry_segments))
            ]
            document.recompute()
        _attach(existing, piece, document)
        from freecad_cloth.common.GarmentDocument import link_garment_object

        link_garment_object(existing, "PatternSketch", document)
        return existing

    sketch = document.addObject(
        "Sketcher::SketchObject", "PatternSketch_" + piece.id.replace("-", "_")
    )
    sketch.Label = piece.name + " (Sketch)"
    sketch.addProperty("App::PropertyString", "PatternPieceId", "Cloth Pattern")
    sketch.PatternPieceId = piece.id
    sketch.addProperty("App::PropertyStringList", "SemanticEdgeIds", "Cloth Pattern")
    edge_count = len(geometry_segments) if geometry_segments is not None else len(piece.outline)
    sketch.SemanticEdgeIds = [f"{piece.id}:edge:{i}" for i in range(edge_count)]
    sketch.addProperty("App::PropertyString", "GeometryAuthority", "Cloth Pattern")
    sketch.GeometryAuthority = "Sketcher"
    sketch.addProperty("App::PropertyString", "GeometrySource", "Cloth Pattern")
    sketch.GeometrySource = "ClothPattern.PatternPiece"
    if geometry_segments is None:
        _add_geometry(sketch, piece.outline)
    else:
        _add_native_geometry(sketch, geometry_segments)
    _attach(sketch, piece, document)
    from freecad_cloth.common.GarmentDocument import link_garment_object

    link_garment_object(sketch, "PatternSketch", document)
    document.recompute()
    return sketch


def _attach(sketch, piece, document):
    obj = _piece_object(document, piece.id)
    if obj is not None:
        _ensure_piece_properties(obj)
        from freecad_cloth.pattern.SketchAuthority import attach

        attach(obj, sketch)
        obj.Visibility = False
        sketch.Visibility = True
    return sketch


def sync_sketch_from_piece(sketch, piece):
    """Replace sketch geometry from a PatternPiece for migration/repair only."""
    piece.validate()
    if getattr(sketch, "PatternPieceId", None) != piece.id:
        msg = "sketch does not belong to pattern piece"
        raise ValueError(msg)
    sketch.clear()
    _add_geometry(sketch, piece.outline)
    sketch.SemanticEdgeIds = [f"{piece.id}:edge:{i}" for i in range(len(piece.outline))]
    sketch.GeometryAuthority = "Sketcher"
    sketch.Document.recompute()
    return sketch
