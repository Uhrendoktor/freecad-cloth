"""Commands for the Cloth Pattern workbench."""
import ast


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
    obj.Width = float(width); obj.Height = float(height)
    obj.SeamAllowance = float(allowance); obj.GrainlineAngle = float(grainline)
    obj.GeometryMode = "Rectangle"; obj.Label = name
    doc.recompute()
    return obj


def create_pattern_piece():
    """Create a 100 x 60 mm parametric demo pattern piece."""
    return create_pattern_piece_from_parameters("PatternPiece", 100.0, 60.0, 0.0, 0.0)


def _selected_piece():
    import FreeCADGui as Gui
    return next((o for o in Gui.Selection.getSelection() if getattr(o, "PatternType", "") == "PatternPiece"), None)


def _create_native_sketch_for_piece(obj):
    """Create/link the native Sketcher representation for a PatternPiece."""
    import FreeCAD as App
    from PatternModel import PatternPiece
    from PatternSketch import create_sketch_for_piece
    try:
        points = [(float(p[0]), float(p[1])) for p in ast.literal_eval(str(obj.SewingOutline))]
    except (ValueError, SyntaxError, TypeError, IndexError):
        raise ValueError("selected pattern piece has no valid sewing outline")
    piece = PatternPiece(obj.Label, points,
                         seam_allowance=float(getattr(obj, "SeamAllowance", 0.0)),
                         grainline_angle=float(getattr(obj, "GrainlineAngle", 0.0)),
                         id=str(obj.PieceId))
    return create_sketch_for_piece(piece, App.ActiveDocument)


def create_pattern_piece_with_sketch():
    """Create a pattern piece and immediately attach its native Sketcher geometry."""
    import FreeCAD as App
    obj = create_pattern_piece(); _create_native_sketch_for_piece(obj)
    App.ActiveDocument.recompute()
    return obj


def edit_pattern_piece():
    """Open the garment-piece properties task panel for the selected piece."""
    obj = _selected_piece()
    if obj is None:
        raise ValueError("select a pattern piece before editing it")
    from PatternGui import show_pattern_piece_task
    show_pattern_piece_task(obj)


def edit_pattern_sketch():
    """Enter the native FreeCAD Sketcher editor for the selected pattern piece."""
    obj = _selected_piece()
    if obj is None:
        raise ValueError("select a pattern piece before editing its sketch")
    sketch = getattr(obj, "Sketch", None)
    if sketch is None:
        sketch = _create_native_sketch_for_piece(obj)
    from PatternSketch import edit_sketch
    return edit_sketch(sketch)


def create_pattern_sketch():
    """Create a native Sketcher representation of the selected pattern piece."""
    obj = _selected_piece()
    if obj is None:
        raise ValueError("select a pattern piece before creating its Sketcher representation")
    return _create_native_sketch_for_piece(obj)


def validate_pattern_piece():
    """Validate the selected piece and show its persistent topology diagnostics."""
    obj = _selected_piece()
    if obj is None:
        raise ValueError("select a pattern piece before validating it")
    from PatternValidation import validate_piece, show_pattern_validation_task
    result = validate_piece(obj)
    show_pattern_validation_task(obj, result)
    return result


def create_pattern_piece_task():
    """Open a task panel for creating a new pattern piece."""
    from PatternGui import show_pattern_piece_task
    show_pattern_piece_task()


def create_pattern_drafting():
    """Open the legacy sketch-like polygon canvas for compatibility/migration."""
    import FreeCAD as App
    from PatternGui import show_pattern_drafting_task
    obj = _selected_piece()
    if obj is None:
        pieces = [o for o in App.ActiveDocument.Objects if getattr(o, "PatternType", "") == "PatternPiece"]
        obj = pieces[0] if pieces else None
    if obj is None:
        raise ValueError("create a pattern piece before opening the drafting canvas")
    return show_pattern_drafting_task(obj)


def show_pattern_2d():
    """Switch the active document to a top-down 2D drafting view."""
    from PatternGui import show_pattern_view
    show_pattern_view()


def create_custom_pattern_piece():
    """Create a larger parametric pattern piece for drafting."""
    return create_pattern_piece_from_parameters("PatternPiece_Large", 180.0, 120.0, 0.0, 0.0)


def create_pattern_mesh():
    """Generate a solver-ready surface mesh for the selected pattern."""
    import FreeCAD as App
    from PatternGeometry import LineSegment, ParametricPattern
    from PatternMesh import triangulate
    from PatternObjects import add_pattern_mesh
    doc = App.ActiveDocument or App.newDocument("ClothPattern")
    piece = _selected_piece()
    if piece is None:
        raise ValueError("create a pattern piece before creating a cloth mesh")
    points = [(float(p[0]), float(p[1])) for p in ast.literal_eval(str(piece.SewingOutline))]
    segments = [LineSegment(str(i), points[i], points[(i + 1) % len(points)]) for i in range(len(points))]
    add_pattern_mesh(doc, triangulate(ParametricPattern(segments)), name=f"{piece.Name}_Mesh")
    doc.recompute()


def _selected_seam_edges(doc):
    import FreeCADGui as Gui
    selected = []
    for entry in Gui.Selection.getSelectionEx():
        obj = entry.Object
        if getattr(obj, "PatternType", "") != "PatternPiece": continue
        for sub_name in entry.SubElementNames:
            if str(sub_name).startswith("Edge"):
                try: selected.append((obj, int(str(sub_name)[4:]) - 1))
                except ValueError: pass
    return selected


def add_seam():
    """Mark a seam between two selected pattern edges, or use the first edge of the first two pieces."""
    import FreeCAD as App
    from PatternModel import Seam
    from PatternObjects import add_seam as add_seam_object
    doc = App.ActiveDocument or App.newDocument("ClothPattern")
    selected = _selected_seam_edges(doc)
    if len(selected) >= 2:
        piece_a, edge_a = selected[0]; piece_b, edge_b = selected[1]
    else:
        pieces = [obj for obj in doc.Objects if getattr(obj, "PatternType", "") == "PatternPiece"]
        if len(pieces) < 2: raise ValueError("select two pattern edges or create at least two pattern pieces")
        piece_a, piece_b, edge_a, edge_b = pieces[0], pieces[1], 0, 0
    if piece_a.PieceId == piece_b.PieceId and edge_a == edge_b:
        raise ValueError("a seam cannot connect an edge to itself")
    base = f"{piece_a.PieceId}-e{edge_a}-{piece_b.PieceId}-e{edge_b}"
    existing = {getattr(o, "SeamId", "") for o in doc.Objects}
    seam_id, suffix = base, 2
    while seam_id in existing:
        seam_id = f"{base}-{suffix}"; suffix += 1
    obj = add_seam_object(doc, Seam(str(piece_a.PieceId), edge_a, str(piece_b.PieceId), edge_b, id=seam_id))
    doc.recompute(); return obj


class _FunctionCommand:
    def __init__(self, function): self.function = function
    def Activated(self): return self.function()
    def GetResources(self):
        return {"MenuText": self.function.__name__.replace("_", " ").title(), "ToolTip": self.function.__doc__ or "Cloth pattern command"}


COMMANDS = [
    "ClothPattern_CreatePieceTask", "ClothPattern_EditPiece", "ClothPattern_CreateSketch",
    "ClothPattern_EditSketch", "ClothPattern_ValidatePiece", "ClothPattern_CreatePieceWithSketch",
    "ClothPattern_CreateDrafting", "ClothPattern_Show2D", "ClothPattern_CreatePiece",
    "ClothPattern_CreateCustomPiece", "ClothPattern_CreateMesh", "ClothPattern_AddSeam",
]

try:
    import FreeCADGui as Gui
    if hasattr(Gui, "addCommand"):
        for name, handler in {
            "ClothPattern_CreatePieceTask": create_pattern_piece_task,
            "ClothPattern_EditPiece": edit_pattern_piece,
            "ClothPattern_CreateSketch": create_pattern_sketch,
            "ClothPattern_EditSketch": edit_pattern_sketch,
            "ClothPattern_ValidatePiece": validate_pattern_piece,
            "ClothPattern_CreatePieceWithSketch": create_pattern_piece_with_sketch,
            "ClothPattern_CreateDrafting": create_pattern_drafting,
            "ClothPattern_Show2D": show_pattern_2d,
            "ClothPattern_CreatePiece": create_pattern_piece,
            "ClothPattern_CreateCustomPiece": create_custom_pattern_piece,
            "ClothPattern_CreateMesh": create_pattern_mesh,
            "ClothPattern_AddSeam": add_seam,
        }.items():
            Gui.addCommand(name, _FunctionCommand(handler))
except (ImportError, AttributeError):
    pass
