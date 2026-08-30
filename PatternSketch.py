"""FreeCAD-native Sketcher authoring adapter for Cloth Pattern pieces.

Sketcher is the editable geometry authority. PatternPiece stores semantic
identity and derived compatibility data; PatternIR preserves curve kind and
endpoint connectivity for downstream sewing and simulation adapters.
"""


def _piece_object(document, piece_id):
    return next((obj for obj in document.Objects if getattr(obj, "PieceId", "") == str(piece_id)), None)


def _ensure_piece_properties(obj):
    if obj is None:
        return
    if "Sketch" not in obj.PropertiesList:
        obj.addProperty("App::PropertyLink", "Sketch", "Cloth")
    if "GeometryAuthority" not in obj.PropertiesList:
        obj.addProperty("App::PropertyEnumeration", "GeometryAuthority", "Cloth")
        obj.GeometryAuthority = ["PatternParameters", "Sketcher"]
    elif "Sketcher" not in tuple(getattr(obj, "GeometryAuthority", ()) or ()):
        obj.GeometryAuthority = ["PatternParameters", "Sketcher"]
    if "GeometryMode" in obj.PropertiesList and "Sketch" not in tuple(getattr(obj, "GeometryMode", ()) or ()):
        obj.GeometryMode = ["Rectangle", "Custom", "Sketch"]
    if "ValidationStatus" not in obj.PropertiesList:
        obj.addProperty("App::PropertyEnumeration", "ValidationStatus", "Validation")
        obj.ValidationStatus = ["Unknown", "Valid", "Invalid"]
        obj.ValidationStatus = "Unknown"
    if "ValidationMessage" not in obj.PropertiesList:
        obj.addProperty("App::PropertyString", "ValidationMessage", "Validation")


def _add_geometry(sketch, points):
    import FreeCAD as App
    import Part
    import Sketcher
    geometry = []
    for index, start in enumerate(points):
        end = points[(index + 1) % len(points)]
        geometry.append(Part.LineSegment(App.Vector(start[0], start[1], 0), App.Vector(end[0], end[1], 0)))
    sketch.addGeometry(geometry, False)

    # Coincident endpoint constraints keep the boundary topologically closed
    # while leaving dimensional degrees of freedom available to the user.
    constraints = []
    for index in range(len(points)):
        constraints.append(Sketcher.Constraint("Coincident", index, 2, (index + 1) % len(points), 1))
    if len(points) == 4:
        constraints.extend((Sketcher.Constraint("Horizontal", 0), Sketcher.Constraint("Vertical", 1),
                            Sketcher.Constraint("Horizontal", 2), Sketcher.Constraint("Vertical", 3)))
    sketch.addConstraint(constraints)


def create_sketch_for_piece(piece, document=None):
    """Create or return the native Sketcher representation for ``piece``."""
    try:
        import FreeCAD as App
    except ImportError as exc:
        raise RuntimeError("FreeCAD Sketcher is required for PatternSketch") from exc

    document = document or App.ActiveDocument
    if document is None:
        document = App.newDocument("ClothPattern")
    piece.validate()

    existing = next((obj for obj in document.Objects
                     if getattr(obj, "PatternPieceId", "") == str(piece.id)
                     and getattr(obj, "TypeId", "") == "Sketcher::SketchObject"), None)
    if existing is not None:
        _attach(existing, piece, document)
        return existing

    sketch = document.addObject("Sketcher::SketchObject", "PatternSketch_" + piece.id.replace("-", "_"))
    sketch.Label = piece.name + " (Sketch)"
    sketch.addProperty("App::PropertyString", "PatternPieceId", "Cloth Pattern")
    sketch.PatternPieceId = piece.id
    sketch.addProperty("App::PropertyStringList", "SemanticEdgeIds", "Cloth Pattern")
    sketch.SemanticEdgeIds = [f"{piece.id}:edge:{i}" for i in range(len(piece.outline))]
    sketch.addProperty("App::PropertyString", "GeometryAuthority", "Cloth Pattern")
    sketch.GeometryAuthority = "Sketcher"
    sketch.addProperty("App::PropertyString", "GeometrySource", "Cloth Pattern")
    sketch.GeometrySource = "ClothPattern.PatternPiece"
    _add_geometry(sketch, piece.outline)
    _attach(sketch, piece, document)
    document.recompute()
    return sketch


def _attach(sketch, piece, document):
    obj = _piece_object(document, piece.id)
    if obj is not None:
        _ensure_piece_properties(obj)
        from SketchAuthority import attach
        attach(obj, sketch)
        obj.Visibility = False
        sketch.Visibility = True
    return sketch


def edit_sketch(sketch):
    """Enter FreeCAD's native Sketcher editor for a pattern sketch."""
    import FreeCADGui as Gui
    if sketch is None or getattr(sketch, "TypeId", "") != "Sketcher::SketchObject":
        raise ValueError("a native Sketcher pattern sketch is required")
    Gui.activeDocument().setEdit(sketch.Name)
    return sketch


def sync_sketch_from_piece(sketch, piece):
    """Replace sketch geometry from a PatternPiece for migration/repair only."""
    piece.validate()
    if getattr(sketch, "PatternPieceId", None) != piece.id:
        raise ValueError("sketch does not belong to pattern piece")
    sketch.clear()
    _add_geometry(sketch, piece.outline)
    sketch.SemanticEdgeIds = [f"{piece.id}:edge:{i}" for i in range(len(piece.outline))]
    sketch.GeometryAuthority = "Sketcher"
    sketch.Document.recompute()
    return sketch
