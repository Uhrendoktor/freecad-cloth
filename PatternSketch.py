"""Optional FreeCAD Sketcher representation for a semantic PatternPiece.

PatternModel remains authoritative; this module is only a FreeCAD-facing adapter.
"""


def create_sketch_for_piece(piece, document=None):
    """Create a native Sketcher::SketchObject mirroring a PatternPiece outline.

    The adapter records stable semantic IDs in custom properties and deliberately
    avoids adding constraints that would make the Sketcher representation the
    source of truth.
    """
    try:
        import FreeCAD as App
        import Sketcher
    except ImportError as exc:
        raise RuntimeError("FreeCAD Sketcher is required for PatternSketch") from exc

    document = document or App.ActiveDocument
    if document is None:
        document = App.newDocument("ClothPattern")
    piece.validate()
    sketch = document.addObject("Sketcher::SketchObject", "PatternSketch_" + piece.id.replace("-", "_"))
    sketch.Label = piece.name + " (Sketch)"
    sketch.addProperty("App::PropertyString", "PatternPieceId", "Cloth Pattern")
    sketch.PatternPieceId = piece.id
    sketch.addProperty("App::PropertyStringList", "SemanticEdgeIds", "Cloth Pattern")
    sketch.SemanticEdgeIds = [f"{piece.id}:edge:{i}" for i in range(len(piece.outline))]

    points = piece.outline
    for i, start in enumerate(points):
        end = points[(i + 1) % len(points)]
        sketch.addGeometry(App.Vector(start[0], start[1], 0), App.Vector(end[0], end[1], 0), False)

    sketch.addProperty("App::PropertyString", "GeometrySource", "Cloth Pattern")
    sketch.GeometrySource = "PatternModel.PatternPiece"
    document.recompute()
    return sketch


def sync_sketch_from_piece(sketch, piece):
    """Replace sketch geometry from the authoritative PatternPiece outline."""
    piece.validate()
    if getattr(sketch, "PatternPieceId", None) != piece.id:
        raise ValueError("sketch does not belong to pattern piece")
    sketch.clear()
    points = piece.outline
    for i, start in enumerate(points):
        end = points[(i + 1) % len(points)]
        import FreeCAD as App
        sketch.addGeometry(App.Vector(start[0], start[1], 0), App.Vector(end[0], end[1], 0), False)
    sketch.SemanticEdgeIds = [f"{piece.id}:edge:{i}" for i in range(len(points))]
    sketch.Document.recompute()
    return sketch
