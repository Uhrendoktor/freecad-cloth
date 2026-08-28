"""Initial commands for the pattern workbench."""

def create_pattern_piece():
    import FreeCAD as App
    from PatternModel import PatternPiece
    from PatternObjects import add_pattern_piece
    doc = App.ActiveDocument or App.newDocument("ClothPattern")
    add_pattern_piece(doc, PatternPiece("PatternPiece", [(0, 0), (100, 0), (100, 60), (0, 60)]))
    doc.recompute()


def add_seam():
    import FreeCAD as App
    from PatternModel import Seam
    from PatternObjects import add_seam
    doc = App.ActiveDocument or App.newDocument("ClothPattern")
    add_seam(doc, Seam("PatternPiece", 0, "PatternPiece", 1))
    doc.recompute()


COMMANDS = ["ClothPattern_CreatePiece", "ClothPattern_AddSeam"]

try:
    import FreeCADGui as Gui
    Gui.addCommand("ClothPattern_CreatePiece", create_pattern_piece)
    Gui.addCommand("ClothPattern_AddSeam", add_seam)
except ImportError:
    pass
