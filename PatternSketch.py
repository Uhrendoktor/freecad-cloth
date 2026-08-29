"""FreeCAD Sketcher representation and semantic-edge adapter for PatternPiece.

PatternModel remains authoritative in the current compatibility path; this
module is the FreeCAD-facing adapter.  Cloth seam references use persistent
semantic edge IDs rather than storing raw Sketcher EdgeN labels as identity.
"""
from PatternSketchAdapter import EdgeReferenceInvalid, get_sketch_edge_ids, make_edge_ids, resolve_sketch_edge


def create_sketch_for_piece(piece, document=None):
    """Create a native Sketcher::SketchObject mirroring a PatternPiece outline.

    The adapter records stable semantic IDs in custom properties.  IDs remain
    valid for edits that preserve geometry cardinality; topology changes must
    be resolved through :mod:`PatternSketchAdapter` and are never silently
    retargeted.
    """
    try:
        import FreeCAD as App
        import Sketcher  # noqa: F401 - verifies the native workbench is available
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
    sketch.SemanticEdgeIds = make_edge_ids(piece.id, len(piece.outline))
    sketch.addProperty("App::PropertyString", "SemanticEdgeContract", "Cloth Pattern")
    sketch.SemanticEdgeContract = "cloth.semantic-edge/v1"

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
    sketch.SemanticEdgeIds = make_edge_ids(piece.id, len(points))
    sketch.Document.recompute()
    return sketch


def resolve_semantic_edge(sketch, edge_id):
    """Resolve a Cloth edge ID to the current Sketcher geometry index.

    ``EdgeReferenceInvalid`` is intentionally exposed to Sewing callers so an
    invalid seam can be reported as a document problem instead of being
    silently redirected to another edge.
    """
    return resolve_sketch_edge(sketch, edge_id)


def semantic_edge_ids(sketch):
    """Return the persisted semantic edge IDs for a native sketch."""
    return get_sketch_edge_ids(sketch)


def semantic_edges_valid(sketch):
    """Return ``(True, '')`` or ``(False, reason)`` for the current topology."""
    try:
        ids = get_sketch_edge_ids(sketch)
        geometry = getattr(sketch, "Geometry", None)
        if geometry is None:
            raise EdgeReferenceInvalid("sketch does not expose Geometry")
        if len(ids) != len(geometry):
            raise EdgeReferenceInvalid(
                f"stored semantic edge count ({len(ids)}) differs from "
                f"Sketcher geometry count ({len(geometry)})"
            )
    except EdgeReferenceInvalid as exc:
        return False, str(exc)
    return True, ""
