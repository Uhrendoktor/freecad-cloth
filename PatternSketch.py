"""FreeCAD Sketcher adapter for the semantic PatternPiece layer.

Sketcher owns editable 2D geometry once a PatternPiece links to its sketch;
Cloth retains garment metadata and stable semantic identity outside Sketcher.
"""


def create_sketch_for_piece(piece, document=None):
    """Create a native Sketcher::SketchObject for a semantic PatternPiece."""
    try:
        import FreeCAD as App
        import Sketcher
    except ImportError as exc:
        raise RuntimeError("FreeCAD Sketcher is required for PatternSketch") from exc

    document = document or App.ActiveDocument
    if document is None:
        document = App.newDocument("ClothPattern")
    piece.validate()
    object_name = "PatternSketch_" + piece.id.replace("-", "_")
    existing = document.getObject(object_name)
    if existing is not None:
        return existing
    sketch = document.addObject("Sketcher::SketchObject", object_name)
    sketch.Label = piece.name + " (Sketch)"
    sketch.addProperty("App::PropertyString", "PatternPieceId", "Cloth Pattern")
    sketch.PatternPieceId = piece.id
    sketch.addProperty("App::PropertyStringList", "SemanticEdgeIds", "Cloth Pattern")
    sketch.SemanticEdgeIds = [f"{piece.id}:edge:{i}" for i in range(len(piece.outline))]
    sketch.addProperty("App::PropertyString", "GeometryAuthority", "Cloth Pattern")
    sketch.GeometryAuthority = "Sketcher"
    sketch.addProperty("App::PropertyString", "GeometrySource", "Cloth Pattern")
    sketch.GeometrySource = "Cloth.PatternPiece"

    points = piece.outline
    for i, start in enumerate(points):
        end = points[(i + 1) % len(points)]
        sketch.addGeometry(App.Vector(start[0], start[1], 0), App.Vector(end[0], end[1], 0), False)

    document.recompute()
    return sketch


def sync_sketch_from_piece(sketch, piece):
    """Legacy migration helper; new edits should be made directly in Sketcher."""
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
