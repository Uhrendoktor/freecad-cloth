"""Validation service for native FreeCAD garment pattern authoring.

Validation is deliberately read-only with respect to geometry. The Sketcher
object remains the source of truth; this module only reports whether the
current authored boundary can be converted to the solver-neutral PatternIR.
"""


def _ensure_properties(obj):
    if "ValidationStatus" not in obj.PropertiesList:
        obj.addProperty("App::PropertyEnumeration", "ValidationStatus", "Validation")
        obj.ValidationStatus = ["Unknown", "Valid", "Invalid"]
    if "ValidationMessage" not in obj.PropertiesList:
        obj.addProperty("App::PropertyString", "ValidationMessage", "Validation")


def validate_piece(obj):
    """Validate one PatternPiece and persist the diagnostic state.

    Returns a dictionary suitable for task-panel presentation. No derived
    geometry is made authoritative by this function.
    """
    _ensure_properties(obj)
    try:
        from PatternModel import PatternPiece
        from PatternIR import PatternIR
        from SeamGraph import SeamGraph

        if str(getattr(obj, "GeometryAuthority", "")) != "Sketcher":
            raise ValueError("pattern piece has no native Sketcher geometry authority")
        sketch = getattr(obj, "Sketch", None)
        if sketch is None:
            raise ValueError("pattern piece has no linked Sketcher object")

        piece = PatternPiece(
            str(obj.Label),
            [],
            id=str(obj.PieceId),
            seam_allowance=float(getattr(obj, "SeamAllowance", 0.0)),
            grainline_angle=float(getattr(obj, "GrainlineAngle", 0.0)),
        )
        graph = SeamGraph()
        graph.add_piece(piece)
        ir = PatternIR.from_sketches(graph, {piece.id: sketch}, curve_samples=64)
        boundaries = ir.piece(piece.id).boundaries
        total = sum(boundary.length for boundary in boundaries)
        result = {
            "valid": True,
            "status": "Valid",
            "message": "Closed Sketcher boundary is valid (%d edges, %.2f mm perimeter)." % (len(boundaries), total),
            "edge_count": len(boundaries),
            "perimeter": total,
        }
    except Exception as exc:
        result = {
            "valid": False,
            "status": "Invalid",
            "message": str(exc),
            "edge_count": 0,
            "perimeter": 0.0,
        }

    obj.ValidationStatus = result["status"]
    obj.ValidationMessage = result["message"]
    return result


def validate_selected_piece():
    """Validate the selected pattern piece in the active FreeCAD document."""
    import FreeCAD as App
    import FreeCADGui as Gui

    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("create a pattern document before validating a piece")
    obj = next((candidate for candidate in Gui.Selection.getSelection()
                if getattr(candidate, "PatternType", "") == "PatternPiece"), None)
    if obj is None:
        obj = next((candidate for candidate in doc.Objects
                    if getattr(candidate, "PatternType", "") == "PatternPiece"), None)
    if obj is None:
        raise ValueError("select or create a pattern piece before validating it")
    result = validate_piece(obj)
    doc.recompute()
    return obj, result
