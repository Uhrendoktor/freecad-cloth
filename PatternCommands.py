"""Commands for the Cloth Pattern workbench."""


def create_pattern_piece():
    """Create an editable 100 x 60 mm pattern piece."""
    import FreeCAD as App
    from PatternFeature import add_pattern_feature

    doc = App.ActiveDocument or App.newDocument("ClothPattern")
    add_pattern_feature(doc, "PatternPiece", 100.0, 60.0)
    doc.recompute()


def create_custom_pattern_piece():
    """Create a larger editable pattern-piece example for drafting."""
    import FreeCAD as App
    from PatternFeature import add_pattern_feature

    doc = App.ActiveDocument or App.newDocument("ClothPattern")
    add_pattern_feature(doc, "PatternPiece_Large", 180.0, 120.0)
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
    """Add a seam connecting two existing pattern pieces."""
    import FreeCAD as App
    from PatternModel import Seam
    from PatternObjects import add_seam

    doc = App.ActiveDocument or App.newDocument("ClothPattern")
    pieces = [obj for obj in doc.Objects if getattr(obj, "PatternType", "") == "PatternPiece"]
    if len(pieces) < 2:
        raise ValueError("create at least two pattern pieces before adding a seam")
    seam = Seam(pieces[0].PieceId, 0, pieces[1].PieceId, 0, id=f"{pieces[0].PieceId}-{pieces[1].PieceId}")
    add_seam(doc, seam)
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
    "ClothPattern_CreateCustomPiece",
    "ClothPattern_CreateMesh",
    "ClothPattern_AddSeam",
]

try:
    import FreeCADGui as Gui
    Gui.addCommand("ClothPattern_CreatePiece", _FunctionCommand(create_pattern_piece))
    Gui.addCommand("ClothPattern_CreateCustomPiece", _FunctionCommand(create_custom_pattern_piece))
    Gui.addCommand("ClothPattern_CreateMesh", _FunctionCommand(create_pattern_mesh))
    Gui.addCommand("ClothPattern_AddSeam", _FunctionCommand(add_seam))
except ImportError:
    pass
