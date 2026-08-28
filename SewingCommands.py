"""Commands for the Cloth Sewing workbench."""

def _seams(doc): return [o for o in doc.Objects if getattr(o, "SeamId", "")]
def _selected_seam(doc):
    import FreeCADGui as Gui
    for obj in Gui.Selection.getSelection():
        if getattr(obj, "SeamId", ""): return obj
    seams = _seams(doc)
    if seams: return seams[0]
    raise ValueError("create or select a seam before creating a sewing operation")
def _pieces_by_id(doc): return {getattr(o, "PieceId", ""): o for o in doc.Objects if getattr(o, "PatternType", "") == "PatternPiece"}
def create_sewing_operation():
    import FreeCAD as App
    from SewingObjects import add_sewing_operation
    doc = App.ActiveDocument or App.newDocument("ClothSewing"); seam = _selected_seam(doc); pieces = _pieces_by_id(doc)
    try: piece_a, piece_b = pieces[str(seam.PieceA)], pieces[str(seam.PieceB)]
    except KeyError: raise ValueError("the seam references pattern pieces that are not in the active document")
    index = len([o for o in doc.Objects if getattr(o, "SewingType", "") == "SewingOperation"]) + 1
    obj = add_sewing_operation(doc, seam, piece_a, piece_b, "SewingOperation%d" % index); doc.recompute(); return obj
def edit_sewing_operation():
    import FreeCADGui as Gui
    obj = next((o for o in Gui.Selection.getSelection() if getattr(o, "SewingType", "") == "SewingOperation"), None)
    if obj is None: raise ValueError("select a sewing operation before editing it")
    from SewingGui import show_sewing_task; show_sewing_task(obj)
def validate_seams():
    import FreeCAD as App
    doc = App.ActiveDocument
    if doc is None: return []
    operations = [o for o in doc.Objects if getattr(o, "SewingType", "") == "SewingOperation"]
    for obj in operations: obj.Proxy.execute(obj)
    doc.recompute(); return [(obj.Name, obj.Status, float(obj.LengthDifference)) for obj in operations]
def show_sewing_2d():
    import FreeCADGui as Gui
    if Gui.activeDocument(): Gui.activeDocument().activeView().viewTop(); Gui.activeDocument().activeView().fitAll()
class _FunctionCommand:
    def __init__(self, function): self.function = function
    def Activated(self): self.function()
    def GetResources(self): return {"MenuText": self.function.__name__.replace("_", " ").title(), "ToolTip": self.function.__doc__ or "Cloth sewing command"}
COMMANDS = ["ClothSewing_CreateOperation", "ClothSewing_EditOperation", "ClothSewing_Validate", "ClothSewing_Show2D"]
try:
    import FreeCADGui as Gui
    if hasattr(Gui, "addCommand"):
        Gui.addCommand("ClothSewing_CreateOperation", _FunctionCommand(create_sewing_operation)); Gui.addCommand("ClothSewing_EditOperation", _FunctionCommand(edit_sewing_operation)); Gui.addCommand("ClothSewing_Validate", _FunctionCommand(validate_seams)); Gui.addCommand("ClothSewing_Show2D", _FunctionCommand(show_sewing_2d))
except (ImportError, AttributeError): pass
