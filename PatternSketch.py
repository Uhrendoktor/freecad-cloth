"""FreeCAD-native Sketcher authoring adapter for Cloth Pattern pieces.

Sketcher is the editable geometry authority. PatternPiece stores semantic
identity and derived compatibility data; PatternIR preserves curve kind and
endpoint connectivity for downstream sewing and simulation adapters.

This module intentionally has only one geometry direction during normal use:
Sketcher -> Cloth. ``sync_sketch_from_piece`` is an explicit migration/repair
operation and is never called by recompute.
"""

from SketcherPatternContract import configure_authority, ensure_semantic_edge_ids


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
        configure_authority(existing, piece.id)
        _attach(existing, piece, document)
        return existing

    sketch = document.addObject("Sketcher::SketchObject", "PatternSketch_" + piece.id.replace("-", "_"))
    sketch.Label = piece.name + " (Sketch)"
    configure_authority(sketch, piece.id)
    _add_geometry(sketch, piece.outline)
    # Geometry is created after the contract metadata, so initialize the
    # geometry-aligned IDs again to make the persisted mapping explicit.
    ensure_semantic_edge_ids(sketch, piece.id)
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


def sync_sketch_from_piece(sketch, piece):
    """Replace sketch geometry from a PatternPiece for migration/repair only.

    This is deliberately not part of the recompute path. Once a piece is
    Sketcher-authoritative, normal edits must flow from the native sketch into
    derived Cloth state, never back into the sketch.
    """
    piece.validate()
    if getattr(sketch, "PatternPieceId", None) != piece.id:
        raise ValueError("sketch does not belong to pattern piece")
    sketch.clear()
    _add_geometry(sketch, piece.outline)
    sketch.SemanticEdgeIds = [f"{piece.id}:edge:{i}" for i in range(len(piece.outline))]
    configure_authority(sketch, piece.id)
    sketch.Document.recompute()
    return sketch
