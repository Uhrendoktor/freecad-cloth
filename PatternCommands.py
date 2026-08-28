"""Commands for the pattern workbench."""


def create_pattern_piece():
    """Create a 100 x 60 mm parametric demo pattern piece."""
    import FreeCAD as App
    from PatternModel import PatternPiece
    from PatternObjects import add_pattern_piece
    from PatternGeometry import rectangle

    doc = App.ActiveDocument or App.newDocument("ClothPattern")
    geometry = rectangle(100.0, 60.0)
    piece = PatternPiece("PatternPiece", geometry.sampled_outline(), id="pattern-piece-1")
    add_pattern_piece(doc, piece)
    doc.recompute()


def create_pattern_mesh():
    """Generate a solver-ready surface mesh for a demonstration pattern."""
    import FreeCAD as App
    from PatternGeometry import rectangle
    from PatternMesh import triangulate
    from PatternObjects import add_pattern_mesh

    doc = App.ActiveDocument or App.newDocument("ClothPattern")
    add_pattern_mesh(doc, triangulate(rectangle(100.0, 60.0)))
    doc.recompute()


def add_seam():
    """Create a sample seam record with stable semantic identity."""
    import FreeCAD as App
    from PatternModel import Seam
    from PatternObjects import add_seam
    doc = App.ActiveDocument or App.newDocument("ClothPattern")
    add_seam(doc, Seam("PatternPiece", 0, "PatternPiece", 1, id="sample-seam"))
    doc.recompute()


class _FunctionCommand:
    def __init__(self, function):
        self.function = function

    def Activated(self):
        self.function()

    def GetResources(self):
        return {
            "MenuText": self.function.__name__.replace("_", " ").title(),
            "ToolTip": self.function.__doc__ or "Cloth pattern command",
        }


COMMANDS = [
    "ClothPattern_CreatePiece",
    "ClothPattern_CreateMesh",
    "ClothPattern_AddSeam",
]

try:
    import FreeCADGui as Gui
    Gui.addCommand("ClothPattern_CreatePiece", _FunctionCommand(create_pattern_piece))
    Gui.addCommand("ClothPattern_CreateMesh", _FunctionCommand(create_pattern_mesh))
    Gui.addCommand("ClothPattern_AddSeam", _FunctionCommand(add_seam))
except ImportError:
    pass
