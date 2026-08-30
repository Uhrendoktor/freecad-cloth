"""Headless contract tests for Cloth Pattern command UX."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PatternCommands import _MENU_TEXT, _PatternCommand, _selected_pattern_piece


def test_pattern_command_has_stable_explicit_label():
    command = _PatternCommand(lambda: 7, lambda: True, "Open Pattern Drafting")
    assert command.IsActive() is True
    assert command.Activated() == 7
    assert command.GetResources()["MenuText"] == "Open Pattern Drafting"


def test_pattern_commands_use_public_workflow_labels():
    assert _MENU_TEXT == {
        "ClothPattern_CreatePieceTask": "Create Pattern Piece",
        "ClothPattern_EditPiece": "Edit Pattern Piece",
        "ClothPattern_CreateSketch": "Create Sketcher Geometry",
        "ClothPattern_CreatePieceWithSketch": "Create Pattern Piece with Sketch",
        "ClothPattern_CreateDrafting": "Open Pattern Drafting",
        "ClothPattern_Show2D": "Show Pattern 2D",
        "ClothPattern_CreatePiece": "Create Pattern Piece (Default)",
        "ClothPattern_CreateCustomPiece": "Create Pattern Piece (Large)",
        "ClothPattern_CreateMesh": "Create Pattern Mesh",
        "ClothPattern_AddSeam": "Add Seam",
    }


def test_selected_pattern_piece_is_contextual(monkeypatch):
    class Selection:
        def __init__(self, objects):
            self._objects = objects

        def getSelection(self):
            return self._objects

    class Piece:
        PatternType = "PatternPiece"

    piece = Piece()
    gui = type("Gui", (), {"Selection": Selection([piece])})
    monkeypatch.setitem(sys.modules, "FreeCADGui", gui)
    assert _selected_pattern_piece() is piece


def test_selected_pattern_piece_ignores_non_pattern_objects(monkeypatch):
    class Selection:
        def getSelection(self):
            return [type("Other", (), {"PatternType": "Seam"})()]

    gui = type("Gui", (), {"Selection": Selection()})
    monkeypatch.setitem(sys.modules, "FreeCADGui", gui)
    assert _selected_pattern_piece() is None
