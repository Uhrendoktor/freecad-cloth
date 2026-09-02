"""Regression tests for Pattern workbench mark command enablement."""
import sys
import types

import freecad_cloth.pattern.PatternMarks as PatternMarks


class _Selection:
    def __init__(self, objects=()):
        self.objects = list(objects)

    def getSelection(self):
        return list(self.objects)


class _Piece:
    PatternType = "PatternPiece"


class _Other:
    PatternType = "Other"


def _set_gui(selection):
    sys.modules["FreeCADGui"] = types.SimpleNamespace(Selection=selection)


def test_marks_require_selected_pattern_piece():
    commands = [
        PatternMarks._FunctionCommand(PatternMarks.add_notch),
        PatternMarks._FunctionCommand(PatternMarks.add_grainline),
        PatternMarks._FunctionCommand(PatternMarks.add_internal_mark),
    ]
    selection = _Selection([_Other()])
    _set_gui(selection)
    assert all(not command.IsActive() for command in commands)

    selection.objects = [_Piece()]
    assert all(command.IsActive() for command in commands)


def test_command_enablement_is_safe_without_freecad_gui():
    sys.modules.pop("FreeCADGui", None)
    command = PatternMarks._FunctionCommand(PatternMarks.add_notch)
    assert command.IsActive()


if __name__ == "__main__":
    test_marks_require_selected_pattern_piece()
    test_command_enablement_is_safe_without_freecad_gui()
    print("Pattern mark enablement checks passed")
