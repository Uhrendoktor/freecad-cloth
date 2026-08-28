"""Commands for the Cloth Pattern workbench."""

def create_pattern_piece_from_parameters(name, width, height, allowance, grainline):
    import FreeCAD as App
    from PatternModel import PatternPiece
    from PatternObjects import add_pattern_piece
    from PatternGeometry import rectangle
    doc = App.ActiveDocument or App.newDocument("ClothPattern")
    geometry = rectangle(float(width), float(height))
    piece_id = "pattern-piece-" + str(len([o for o in doc.Objects if getattr(o, "PatternType", "") == "PatternPiece"]) + 1)
    piece = PatternPiece(name, geometry.sampled_outline(), id=piece_id, seam_allowance=float(allowance), grainline_angle=float(grainline))
    obj = add_pattern_piece(doc, piece)
    obj.Width = float(width); obj.Height = float(height); obj.SeamAllowance = float(allowance); obj.GrainlineAngle = float(grainline); obj.Label = name
    doc.recompute()
    return obj

def create_pattern_piece():
    """Create a 100 x 60 mm parametric demo pattern piece."""
    return create_pattern_piece_from_parameters("PatternPiece", 100.0, 60.0, 0.0, 0.0)

def edit_pattern_piece():
    """Open the Pattern Piece task panel for the selected piece."""
    import FreeCADGui as Gui
    selection = Gui.Selection.getSelection()
    obj = next((o for o in selection if getattr(o, "PatternType", "") == "PatternPiece"), None)
    if obj is None: raise ValueError("select a pattern piece before editing it")
    from PatternGui import show_pattern_piece_task
    show_pattern_piece_task(obj)

def create_pattern_piece_task():
    """Open a task panel for creating a new pattern piece."""
    from PatternGui import show_pattern_piece_task
    show_pattern_piece_task()

def open_pattern_drafting():
    """Open the interactive 2D drafting canvas for the selected piece."""
    import FreeCADGui as Gui
    obj = next((o for o in Gui.Selection.getSelection() if getattr(o, "PatternType", "") == "PatternPiece"), None)
    from PatternGui import show_pattern_drafting_task
    show_pattern_drafting_task(obj)

def show_pattern_2d():
    """Switch the active document to a top-down 2D drafting view."""
    from PatternGui import show_pattern_view
    show_pattern_view()

def create_custom_pattern_piece():
    """Create a second, larger parametric pattern piece for drafting."""
    return create_pattern_piece_from_parameters("PatternPiece_Large", 180.0, 120.0, 0.0, 0.0)

def create_pattern_mesh():
    """Generate a solver-ready surface mesh for a demonstration pattern."""
    import FreeCAD as App
    from PatternGeometry import rectangle
    from PatternMesh import triangulate
    from PatternObjects import add_pattern_mesh
    doc = App.ActiveDocument or App.newDocument("ClothPattern")
    add_pattern_mesh(doc, triangulate(rectangle(100.0, 60.0))); doc.recompute()

def add_seam():
    """Create a seam between the first two pattern pieces in the document."""
    import FreeCAD as App
    from PatternModel import Seam
    from PatternObjects import add_seam
    doc = App.ActiveDocument or App.newDocument("ClothPattern")
    pieces = [obj for obj in doc.Objects if getattr(obj, "PatternType", "") == "PatternPiece"]
    if len(pieces) < 2: raise ValueError("create at least two pattern pieces before adding a seam")
    piece_a, piece_b = pieces[:2]
    add_seam(doc, Seam(piece_a.PieceId, 0, piece_b.PieceId, 0, id=f"{piece_a.PieceId}-{piece_b.PieceId}")); doc.recompute()

class _FunctionCommand:
    def __init__(self, function): self.function = function
    def Activated(self): self.function()
    def GetResources(self): return {"MenuText": self.function.__name__.replace("_", " ").title(), "ToolTip": self.function.__doc__ or "Cloth pattern command"}

COMMANDS = [
    "ClothPattern_CreatePieceTask", "ClothPattern_EditPiece", "ClothPattern_OpenDrafting",
    "ClothPattern_Show2D", "ClothPattern_CreatePiece", "ClothPattern_CreateCustomPiece",
    "ClothPattern_CreateMesh", "ClothPattern_AddSeam",
]

try:
    import FreeCADGui as Gui
    if hasattr(Gui, "addCommand"):
        Gui.addCommand("ClothPattern_CreatePieceTask", _FunctionCommand(create_pattern_piece_task))
        Gui.addCommand("ClothPattern_EditPiece", _FunctionCommand(edit_pattern_piece))
        Gui.addCommand("ClothPattern_OpenDrafting", _FunctionCommand(open_pattern_drafting))
        Gui.addCommand("ClothPattern_Show2D", _FunctionCommand(show_pattern_2d))
        Gui.addCommand("ClothPattern_CreatePiece", _FunctionCommand(create_pattern_piece))
        Gui.addCommand("ClothPattern_CreateCustomPiece", _FunctionCommand(create_custom_pattern_piece))
        Gui.addCommand("ClothPattern_CreateMesh", _FunctionCommand(create_pattern_mesh))
        Gui.addCommand("ClothPattern_AddSeam", _FunctionCommand(add_seam))
except (ImportError, AttributeError):
    pass
