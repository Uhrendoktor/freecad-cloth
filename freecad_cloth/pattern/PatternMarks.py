"""Persisted semantic marks for the Cloth Pattern workbench."""
from freecad_cloth.common.CommandAdapter import icon_for_command


def _pieces(doc):
    return [o for o in doc.Objects if getattr(o, "PatternType", "") == "PatternPiece"]


def _selected_piece(doc):
    try:
        import FreeCADGui as Gui
        for obj in Gui.Selection.getSelection():
            if getattr(obj, "PatternType", "") == "PatternPiece":
                return obj
    except ImportError:
        pass
    pieces = _pieces(doc)
    if pieces:
        return pieces[0]
    raise ValueError("create or select a pattern piece before adding a mark")


def _default_segment_id(piece):
    """Return the first authoritative semantic edge for persisted construction marks."""
    sketch = getattr(piece, "Sketch", None)
    if str(getattr(piece, "GeometryAuthority", "")).strip() == "Sketcher" and sketch is not None:
        semantic_ids = tuple(str(value).strip() for value in getattr(sketch, "SemanticEdgeIds", ()) or ())
        for value in semantic_ids:
            if value:
                return value
    from freecad_cloth.pattern.PatternObjects import _edge_records
    records = _edge_records(piece)
    if records:
        return str(records[0]["id"])
    raise ValueError("pattern piece has no authoritative semantic edge for construction mark")


def _has_selected_piece():
    try:
        import FreeCADGui as Gui
        return any(getattr(obj, "PatternType", "") == "PatternPiece" for obj in Gui.Selection.getSelection())
    except (ImportError, AttributeError):
        return True


def add_mark(doc, mark_type, piece_id, segment_id="", position=0.5, depth=3.0, angle=0.0, length=40.0, text=""):
    if not mark_type.strip():
        raise ValueError("mark type must not be empty")
    if not piece_id.strip():
        raise ValueError("mark piece ID must not be empty")
    if not 0.0 <= float(position) <= 1.0:
        raise ValueError("mark position must be between 0 and 1")
    if float(depth) <= 0:
        raise ValueError("mark depth must be positive")
    if float(length) <= 0:
        raise ValueError("mark length must be positive")
    name = "%s_%d" % (mark_type, 1 + len([o for o in doc.Objects if getattr(o, "PatternMarkType", "") == mark_type]))
    obj = doc.addObject("App::FeaturePython", name)
    obj.Label = text.strip() or name
    obj.addProperty("App::PropertyString", "PatternMarkId", "Pattern Mark").PatternMarkId = name
    obj.addProperty("App::PropertyString", "PatternMarkType", "Pattern Mark").PatternMarkType = mark_type
    obj.addProperty("App::PropertyString", "PieceId", "Pattern Mark").PieceId = piece_id
    obj.addProperty("App::PropertyString", "SegmentId", "Pattern Mark").SegmentId = segment_id
    obj.addProperty("App::PropertyFloat", "Position", "Pattern Mark").Position = float(position)
    obj.addProperty("App::PropertyLength", "Depth", "Pattern Mark").Depth = float(depth)
    obj.addProperty("App::PropertyAngle", "Angle", "Pattern Mark").Angle = float(angle)
    obj.addProperty("App::PropertyLength", "Length", "Pattern Mark").Length = float(length)
    obj.addProperty("App::PropertyString", "Text", "Pattern Mark").Text = text.strip()
    return obj


def add_notch():
    import FreeCAD as App
    doc = App.ActiveDocument or App.newDocument("ClothPattern")
    piece = _selected_piece(doc)
    return add_mark(doc, "Notch", str(piece.PieceId), _default_segment_id(piece), 0.5, depth=3.0)


def add_grainline():
    import FreeCAD as App
    doc = App.ActiveDocument or App.newDocument("ClothPattern")
    piece = _selected_piece(doc)
    length = max(10.0, min(float(piece.Width), float(piece.Height)) * 0.6)
    return add_mark(doc, "Grainline", str(piece.PieceId), _default_segment_id(piece), angle=float(piece.GrainlineAngle), length=length)


def add_internal_mark():
    import FreeCAD as App
    doc = App.ActiveDocument or App.newDocument("ClothPattern")
    piece = _selected_piece(doc)
    return add_mark(doc, "InternalMark", str(piece.PieceId), _default_segment_id(piece), 0.5, depth=3.0, text="Internal mark")


class _FunctionCommand:
    def __init__(self, function, command_name):
        self.function = function
        self.command_name = command_name

    def Activated(self):
        obj = self.function()
        if hasattr(obj, "Document"):
            obj.Document.recompute()

    def IsActive(self):
        return _has_selected_piece()

    def GetResources(self):
        return {
            "MenuText": self.function.__name__.replace("_", " ").title(),
            "ToolTip": self.function.__doc__ or "Cloth pattern mark command",
            "Pixmap": icon_for_command(self.command_name),
        }


COMMANDS = ["ClothPattern_AddNotch", "ClothPattern_AddGrainline", "ClothPattern_AddInternalMark"]

try:
    import FreeCADGui as Gui
    if hasattr(Gui, "addCommand"):
        Gui.addCommand("ClothPattern_AddNotch", _FunctionCommand(add_notch, "ClothPattern_AddNotch"))
        Gui.addCommand("ClothPattern_AddGrainline", _FunctionCommand(add_grainline, "ClothPattern_AddGrainline"))
        Gui.addCommand("ClothPattern_AddInternalMark", _FunctionCommand(add_internal_mark, "ClothPattern_AddInternalMark"))
except (ImportError, AttributeError):
    pass
