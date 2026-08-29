"""Commands for the Cloth Sewing workbench."""


def _seams(doc):
    return [o for o in doc.Objects if getattr(o, "SeamId", "")]


def _selected_seam(doc):
    import FreeCADGui as Gui
    for obj in Gui.Selection.getSelection():
        if getattr(obj, "SeamId", ""):
            return obj
    seams = _seams(doc)
    if seams:
        return seams[0]
    raise ValueError("create or select a seam before creating a sewing operation")


def _pieces_by_id(doc):
    return {getattr(o, "PieceId", ""): o for o in doc.Objects if getattr(o, "PatternType", "") == "PatternPiece"}


def _selected_pattern_edges():
    """Return exactly two selected pattern-piece edge references."""
    import FreeCADGui as Gui

    edges = []
    for selection in Gui.Selection.getSelectionEx():
        obj = selection.Object
        if getattr(obj, "PatternType", "") != "PatternPiece":
            continue
        for sub_name in selection.SubElementNames:
            if str(sub_name).startswith("Edge"):
                try:
                    edge = int(str(sub_name)[4:]) - 1
                except ValueError:
                    continue
                edges.append((obj, edge))
    if len(edges) != 2:
        raise ValueError("select exactly two edges on pattern pieces to create a seam")
    if edges[0][0] is edges[1][0]:
        raise ValueError("a seam must connect two different pattern pieces")
    return edges


def create_seam_from_selection():
    """Create a persistent canonical seam from two selected pattern edges."""
    import FreeCAD as App
    from PatternModel import Seam
    from PatternObjects import add_seam

    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before creating a seam")
    (piece_a, edge_a), (piece_b, edge_b) = _selected_pattern_edges()
    prefix = "seam-%d" % (len(_seams(doc)) + 1)
    seam_model = Seam(
        str(piece_a.PieceId), edge_a, str(piece_b.PieceId), edge_b, id=prefix
    )
    seam = add_seam(doc, seam_model)
    doc.recompute()
    return seam


def create_sewing_operation():
    import FreeCAD as App
    from SewingObjects import add_sewing_operation

    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    seam = _selected_seam(doc)
    pieces = _pieces_by_id(doc)
    try:
        a, b = pieces[str(seam.PieceA)], pieces[str(seam.PieceB)]
    except KeyError:
        raise ValueError("the seam references pattern pieces that are not in the active document")
    n = len([o for o in doc.Objects if getattr(o, "SewingType", "") == "SewingOperation"]) + 1
    obj = add_sewing_operation(doc, seam, a, b, "SewingOperation%d" % n)
    doc.recompute()
    return obj


def edit_sewing_operation():
    import FreeCADGui as Gui
    obj = next(
        (o for o in Gui.Selection.getSelection() if getattr(o, "SewingType", "") == "SewingOperation"),
        None,
    )
    if obj is None:
        raise ValueError("select a sewing operation before editing it")
    from SewingGui import show_sewing_task
    return show_sewing_task(obj)


def reverse_selected_seam():
    """Toggle B-side seam orientation on the canonical seam."""
    import FreeCAD as App
    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before changing seam orientation")
    seam = _selected_seam(doc)
    seam.ReversedB = not bool(seam.ReversedB)
    doc.recompute()
    return seam


def toggle_selected_alignment():
    """Toggle the canonical seam correspondence between endpoint and uniform alignment."""
    import FreeCAD as App
    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before changing seam alignment")
    seam = _selected_seam(doc)
    seam.Alignment = "uniform" if str(seam.Alignment) == "endpoints" else "endpoints"
    doc.recompute()
    return seam


def validate_seams():
    import FreeCAD as App
    doc = App.ActiveDocument
    if doc is None:
        return []
    ops = [o for o in doc.Objects if getattr(o, "SewingType", "") == "SewingOperation"]
    for obj in ops:
        obj.Proxy.execute(obj)
    doc.recompute()
    return [(o.Name, o.Status, float(o.LengthDifference)) for o in ops]


def show_sewing_2d():
    """Focus the top view on pattern pieces, seams, and stitch correspondence."""
    import FreeCADGui as Gui
    if not Gui.activeDocument():
        return
    Gui.Selection.clearSelection()
    for obj in Gui.activeDocument().Document.Objects:
        if getattr(obj, "SeamId", "") or getattr(obj, "SewingType", "") == "SewingOperation":
            Gui.Selection.addSelection(obj)
    view = Gui.activeDocument().activeView()
    view.viewTop()
    view.fitAll()


COMMANDS = [
    "ClothSewing_CreateSeam",
    "ClothSewing_CreateOperation",
    "ClothSewing_EditOperation",
    "ClothSewing_ReverseSeam",
    "ClothSewing_ToggleAlignment",
    "ClothSewing_Validate",
    "ClothSewing_Show2D",
]

_COMMAND_HANDLERS = {
    "ClothSewing_CreateSeam": create_seam_from_selection,
    "ClothSewing_CreateOperation": create_sewing_operation,
    "ClothSewing_EditOperation": edit_sewing_operation,
    "ClothSewing_ReverseSeam": reverse_selected_seam,
    "ClothSewing_ToggleAlignment": toggle_selected_alignment,
    "ClothSewing_Validate": validate_seams,
    "ClothSewing_Show2D": show_sewing_2d,
}

_TOOLTIPS = {
    "ClothSewing_CreateSeam": "Create a persistent seam from two selected pattern edges",
    "ClothSewing_CreateOperation": "Create a sewing operation from the selected seam",
    "ClothSewing_EditOperation": "Edit seam alignment, orientation, tolerance, and stitch samples",
    "ClothSewing_ReverseSeam": "Reverse the B-side stitch correspondence",
    "ClothSewing_ToggleAlignment": "Toggle endpoint and uniform seam correspondence",
    "ClothSewing_Validate": "Validate sewing operations and report seam length mismatches",
    "ClothSewing_Show2D": "Show pattern, seam, and stitch correspondence in top view",
}


def _has_active_document():
    try:
        import FreeCAD as App
        return App.ActiveDocument is not None
    except ImportError:
        return False


def _has_selected_seam():
    try:
        import FreeCADGui as Gui
        return any(getattr(o, "SeamId", "") for o in Gui.Selection.getSelection())
    except ImportError:
        return False


def _has_selected_operation():
    try:
        import FreeCADGui as Gui
        return any(getattr(o, "SewingType", "") == "SewingOperation" for o in Gui.Selection.getSelection())
    except ImportError:
        return False


class _SewingCommand:
    """FreeCAD command adapter with context-sensitive enablement."""

    def __init__(self, function, active, tooltip):
        self.function = function
        self.active = active
        self.tooltip = tooltip

    def Activated(self):
        return self.function()

    def IsActive(self):
        return bool(self.active())

    def GetResources(self):
        return {
            "MenuText": self.function.__name__.replace("_", " ").title(),
            "ToolTip": self.tooltip,
        }


try:
    import FreeCADGui as Gui

    _ACTIVATION = {
        "ClothSewing_CreateSeam": lambda: _has_active_document(),
        "ClothSewing_CreateOperation": lambda: _has_active_document() and _has_selected_seam(),
        "ClothSewing_EditOperation": lambda: _has_active_document() and _has_selected_operation(),
        "ClothSewing_ReverseSeam": lambda: _has_active_document() and _has_selected_seam(),
        "ClothSewing_ToggleAlignment": lambda: _has_active_document() and _has_selected_seam(),
        "ClothSewing_Validate": lambda: _has_active_document(),
        "ClothSewing_Show2D": lambda: _has_active_document(),
    }
    for name, function in _COMMAND_HANDLERS.items():
        Gui.addCommand(name, _SewingCommand(function, _ACTIVATION[name], _TOOLTIPS[name]))
except (ImportError, AttributeError):
    pass
