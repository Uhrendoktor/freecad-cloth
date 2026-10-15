"""Regression tests for Pattern workbench mark command enablement."""

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


def _commands(gui):
    return [
        PatternMarks._FunctionCommand(PatternMarks.add_notch, "ClothPattern_AddNotch", gui=gui),
        PatternMarks._FunctionCommand(
            PatternMarks.add_grainline, "ClothPattern_AddGrainline", gui=gui
        ),
        PatternMarks._FunctionCommand(
            PatternMarks.add_internal_mark, "ClothPattern_AddInternalMark", gui=gui
        ),
    ]


def test_marks_require_selected_pattern_piece():
    selection = _Selection([_Other()])
    from types import SimpleNamespace

    commands = _commands(SimpleNamespace(Selection=selection))
    assert all(not command.IsActive() for command in commands)

    selection.objects = [_Piece()]
    assert all(command.IsActive() for command in commands)


def test_command_enablement_is_safe_without_freecad_gui():
    command = PatternMarks._FunctionCommand(
        PatternMarks.add_notch, "ClothPattern_AddNotch", gui=None
    )
    assert command.IsActive()


if __name__ == "__main__":
    test_marks_require_selected_pattern_piece()
    test_command_enablement_is_safe_without_freecad_gui()
    print("Pattern mark enablement checks passed")
