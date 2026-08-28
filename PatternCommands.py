"""Commands for the Cloth Pattern workbench."""


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


def create_custom_pattern_piece():
    """Create a second, larger parametric pattern piece for drafting."""
    import FreeCAD as App
    from PatternModel import PatternPiece
    from PatternObjects import add_pattern_piece
    from PatternGeometry import rectangle

    doc = App.ActiveDocument or App.newDocument("ClothPattern")
    geometry = rectangle(180.0, 120.0)
    piece = PatternPiece("PatternPiece_Large", geometry.sampled_outline(), id="pattern-piece-large")
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
    """Create a seam between the first two pattern pieces in the document."""
    import FreeCAD as App
    from PatternModel import Seam
    from PatternObjects import add_seam

    doc = App.ActiveDocument or App.newDocument("ClothPattern")
    pieces = [obj for obj in doc.Objects if getattr(obj, "PatternType", "") == "PatternPiece"]
    if len(pieces) < 2:
        raise ValueError("create at least two pattern pieces before adding a seam")
    piece_a, piece_b = pieces[:2]
    seam = Seam(piece_a.PieceId, 0, piece_b.PieceId, 0, id=f"{piece_a.PieceId}-{piece_b.PieceId}")
    add_seam(doc, seam)
    doc.recompute()


def create_drape_scene():
    """Create and advance a deterministic two-panel 3D drape scene."""
    import FreeCAD as App
    from SimulationObjects import create_drape_scene as _create
    doc = App.ActiveDocument or App.newDocument("ClothDrape")
    return _create(doc)


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
    "ClothSimulation_CreateDrape",
]

try:
    import FreeCADGui as Gui
    if hasattr(Gui, "addCommand"):
        Gui.addCommand("ClothPattern_CreatePiece", _FunctionCommand(create_pattern_piece))
        Gui.addCommand("ClothPattern_CreateCustomPiece", _FunctionCommand(create_custom_pattern_piece))
        Gui.addCommand("ClothPattern_CreateMesh", _FunctionCommand(create_pattern_mesh))
        Gui.addCommand("ClothPattern_AddSeam", _FunctionCommand(add_seam))
        Gui.addCommand("ClothSimulation_CreateDrape", _FunctionCommand(create_drape_scene))
except (ImportError, AttributeError):
    pass
