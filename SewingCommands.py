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
    obj = next((o for o in Gui.Selection.getSelection() if getattr(o, "SewingType", "") == "SewingOperation"), None)
    if obj is None:
        raise ValueError("select a sewing operation before editing it")
    from SewingGui import show_sewing_task
    show_sewing_task(obj)


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
    import FreeCADGui as Gui
    if Gui.activeDocument():
        Gui.activeDocument().activeView().viewTop()
        Gui.activeDocument().activeView().fitAll()


COMMANDS = {
    "ClothSewing_CreateOperation": create_sewing_operation,
    "ClothSewing_EditOperation": edit_sewing_operation,
    "ClothSewing_Validate": validate_seams,
    "ClothSewing_Show2D": show_sewing_2d,
}

try:
    import FreeCADGui as Gui
    from CommandAdapter import register_commands
    register_commands(Gui, COMMANDS)
except (ImportError, AttributeError):
    pass
