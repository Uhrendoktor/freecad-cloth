import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PatternModel import PatternPiece
from PatternSketch import create_sketch_for_piece
from PatternDrafting import parse_points, serialize_points, add_point, remove_point, bounds


def test_pattern_sketch_module_is_headless_safe():
    piece = PatternPiece("Front", [(0.0, 0.0), (100.0, 0.0), (100.0, 60.0), (0.0, 60.0)], id="front")
    piece.validate()
    assert [f"{piece.id}:edge:{i}" for i in range(4)] == ["front:edge:0", "front:edge:1", "front:edge:2", "front:edge:3"]


def test_pattern_sketch_requires_freecad_when_called():
    piece = PatternPiece("Front", [(0.0, 0.0), (100.0, 0.0), (100.0, 60.0)], id="front")
    if "FreeCAD" in sys.modules:
        return
    try:
        create_sketch_for_piece(piece)
    except RuntimeError as exc:
        assert "FreeCAD Sketcher" in str(exc)
    else:
        raise AssertionError("headless environment should not create a native Sketcher object")


def test_one_step_pattern_piece_command_is_registered_and_creates_native_sketch():
    import PatternCommands

    class Document:
        def __init__(self):
            self.recompute_calls = 0

        def recompute(self):
            self.recompute_calls += 1

    document = Document()
    piece = type("PatternPieceObject", (), {
        "Label": "Bodice",
        "PieceId": "pattern-piece-1",
        "SeamAllowance": 8.0,
        "GrainlineAngle": 0.0,
        "SewingOutline": "[(0, 0), (100, 0), (100, 60), (0, 60)]",
    })()
    calls = []
    original_create = PatternCommands.create_pattern_piece
    old_freecad = sys.modules.get("FreeCAD")
    old_sketch = sys.modules.get("PatternSketch")

    PatternCommands.create_pattern_piece = lambda: piece
    sys.modules["FreeCAD"] = type("FreeCAD", (), {"ActiveDocument": document})

    def create_sketch_for_piece(model, doc):
        calls.append((model, doc))
        return "Sketch"

    sys.modules["PatternSketch"] = type("PatternSketch", (), {"create_sketch_for_piece": create_sketch_for_piece})
    try:
        assert "ClothPattern_CreatePieceWithSketch" in PatternCommands.COMMANDS
        result = PatternCommands.create_pattern_piece_with_sketch()
    finally:
        PatternCommands.create_pattern_piece = original_create
        if old_freecad is None:
            sys.modules.pop("FreeCAD", None)
        else:
            sys.modules["FreeCAD"] = old_freecad
        if old_sketch is None:
            sys.modules.pop("PatternSketch", None)
        else:
            sys.modules["PatternSketch"] = old_sketch

    assert result is piece
    assert len(calls) == 1
    model, doc = calls[0]
    assert model.name == "Bodice"
    assert model.outline == [(0.0, 0.0), (100.0, 0.0), (100.0, 60.0), (0.0, 60.0)]
    assert model.seam_allowance == 8.0
    assert model.grainline_angle == 0.0
    assert model.id == "pattern-piece-1"
    assert doc is document
    assert document.recompute_calls == 1


def test_edit_sketch_enters_native_editor_for_selected_piece():
    import PatternCommands

    class SketchObject:
        Name = "PatternSketch_front"

    class Piece:
        PatternType = "PatternPiece"
        Sketch = SketchObject()

    edits = []
    old_gui = sys.modules.get("FreeCADGui")
    gui = type("FreeCADGui", (), {})()
    gui.Selection = type("Selection", (), {"getSelection": staticmethod(lambda: [Piece()])})()
    gui.activeDocument = staticmethod(lambda: type("DocGui", (), {"setEdit": lambda self, name: edits.append(name)})())
    sys.modules["FreeCADGui"] = gui
    try:
        result = PatternCommands.edit_pattern_sketch()
    finally:
        if old_gui is None:
            sys.modules.pop("FreeCADGui", None)
        else:
            sys.modules["FreeCADGui"] = old_gui

    assert result.Name == "PatternSketch_front"
    assert edits == ["PatternSketch_front"]
    assert "ClothPattern_EditSketch" in PatternCommands.COMMANDS


def test_polygon_drafting_round_trip_and_editing():
    points = ((0.0, 0.0), (80.0, 0.0), (100.0, 40.0), (40.0, 70.0), (0.0, 50.0))
    encoded = serialize_points(points)
    assert parse_points(encoded) == points
    edited = add_point(points, 90.0, 20.0, 2)
    assert len(edited) == 6
    edited = remove_point(edited, 2)
    assert edited == points
    assert bounds(points) == (0.0, 0.0, 100.0, 70.0)


if __name__ == "__main__":
    test_pattern_sketch_module_is_headless_safe()
    test_pattern_sketch_requires_freecad_when_called()
    test_one_step_pattern_piece_command_is_registered_and_creates_native_sketch()
    test_edit_sketch_enters_native_editor_for_selected_piece()
    test_polygon_drafting_round_trip_and_editing()
    print("pattern sketch tests passed")
