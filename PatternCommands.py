"""Commands for the pattern workbench."""


def create_pattern_piece():
    import FreeCAD as App
    from PatternModel import PatternPiece
    from PatternObjects import add_pattern_piece
    from PatternGeometry import rectangle

    doc = App.ActiveDocument or App.newDocument("ClothPattern")
    geometry = rectangle(100.0, 60.0)
    outline = geometry.sampled_outline()
    add_pattern_piece(doc, PatternPiece("PatternPiece", outline))
    doc.recompute()


def add_seam():
    import FreeCAD as App
    from PatternModel import Seam
    from PatternObjects import add_seam
    doc = App.ActiveDocument or App.newDocument("ClothPattern")
    add_seam(doc, Seam("PatternPiece", 0, "PatternPiece", 1))
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


COMMANDS = ["ClothPattern_CreatePiece", "ClothPattern_AddSeam"]

try:
    import FreeCADGui as Gui
    Gui.addCommand("ClothPattern_CreatePiece", _FunctionCommand(create_pattern_piece))
    Gui.addCommand("ClothPattern_AddSeam", _FunctionCommand(add_seam))
except ImportError:
    pass
