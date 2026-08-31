"""Focused contracts for the Sketcher-first Pattern authoring path."""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import PatternCommands


def _function(name):
    tree = ast.parse((ROOT / "PatternCommands.py").read_text(encoding="utf-8"))
    return next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)


def test_default_piece_creation_attaches_native_sketch_after_recompute():
    function = _function("create_pattern_piece_from_parameters")
    calls = [
        node for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_ensure_native_sketch_for_piece"
    ]
    assert len(calls) == 1
    assert sum(1 for node in ast.walk(function) if isinstance(node, ast.Attribute) and node.attr == "recompute") == 2


def test_create_piece_command_is_sketcher_first_and_compatibility_alias_remains():
    calls = []
    original = PatternCommands.create_pattern_piece_from_parameters
    PatternCommands.create_pattern_piece_from_parameters = lambda *args: calls.append(args) or "piece"
    try:
        assert PatternCommands.create_pattern_piece() == "piece"
    finally:
        PatternCommands.create_pattern_piece_from_parameters = original
    assert calls == [("PatternPiece", 100.0, 60.0, 0.0, 0.0)]
    assert PatternCommands.create_pattern_piece_with_sketch is not None


def test_edit_piece_public_command_uses_native_sketcher_label():
    command = PatternCommands._FunctionCommand(PatternCommands.edit_sketch)
    resources = command.GetResources()
    assert resources["MenuText"] == "Edit Sketch"
    assert "Sketcher" in resources["ToolTip"]


def test_edit_sketch_enters_linked_native_sketch_without_rebuilding_it():
    class Sketch:
        Name = "PatternSketch_front"
        TypeId = "Sketcher::SketchObject"

    class Piece:
        PatternType = "PatternPiece"
        Sketch = Sketch()

    class Selection:
        @staticmethod
        def getSelection():
            return [Piece()]

    entered = []

    class Gui:
        Selection = Selection

        @staticmethod
        def activeDocument():
            class DocumentGui:
                @staticmethod
                def setEdit(name):
                    entered.append(name)
            return DocumentGui()

    old_gui = sys.modules.get("FreeCADGui")
    sys.modules["FreeCADGui"] = Gui
    try:
        result = PatternCommands.edit_sketch()
    finally:
        if old_gui is None:
            sys.modules.pop("FreeCADGui", None)
        else:
            sys.modules["FreeCADGui"] = old_gui

    assert result.Name == "PatternSketch_front"
    assert entered == ["PatternSketch_front"]


if __name__ == "__main__":
    test_default_piece_creation_attaches_native_sketch_after_recompute()
    test_create_piece_command_is_sketcher_first_and_compatibility_alias_remains()
    test_edit_piece_public_command_uses_native_sketcher_label()
    test_edit_sketch_enters_linked_native_sketch_without_rebuilding_it()
    print("pattern Sketcher-first tests passed")
