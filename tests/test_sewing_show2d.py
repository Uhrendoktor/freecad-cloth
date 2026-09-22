import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freecad_cloth.sewing.SewingCommands import show_sewing_2d
from freecad_cloth.sewing.SewingView import apply_seam_colors, pattern_pieces_for_2d, seam_color_map


def test_2d_focus_includes_only_authoritative_pattern_pieces_in_document_order():
    first = SimpleNamespace(Name="PatternA", PatternType="PatternPiece")
    seam = SimpleNamespace(Name="Seam", SeamId="seam-1")
    second = SimpleNamespace(Name="PatternB", PatternType="PatternPiece")
    operation = SimpleNamespace(Name="Operation", SewingType="SewingOperation")
    assert pattern_pieces_for_2d([first, seam, second, operation]) == [first, second]


def test_2d_focus_ignores_unrelated_objects_without_freecad_runtime():
    objects = [
        SimpleNamespace(Name="Body"),
        SimpleNamespace(Name="Pattern", PatternType="PatternPiece"),
        SimpleNamespace(Name="Sketch"),
    ]
    result = pattern_pieces_for_2d(objects)
    assert [obj.Name for obj in result] == ["Pattern"]


if __name__ == "__main__":
    test_2d_focus_includes_only_authoritative_pattern_pieces_in_document_order()
    test_2d_focus_ignores_unrelated_objects_without_freecad_runtime()
    test_seam_colors_are_distinct_and_stable_by_seam_id()
    test_apply_seam_colors_marks_each_seam_pair()
    test_show_2d_does_not_select_seams_over_their_colors()
    print("sewing Show 2D tests passed")


def test_seam_colors_are_distinct_and_stable_by_seam_id():
    seam_ids = ["seam-3", "seam-1", "seam-2"]
    forward = seam_color_map(seam_ids)
    reverse = seam_color_map(reversed(seam_ids))
    assert forward == reverse
    assert len(set(forward.values())) == len(seam_ids)


def test_apply_seam_colors_marks_each_seam_pair():
    first = SimpleNamespace(SeamId="seam-a", ViewObject=SimpleNamespace(LineColor=None))
    second = SimpleNamespace(SeamId="seam-b", ViewObject=SimpleNamespace(LineColor=None))
    colors = apply_seam_colors([second, first])
    assert first.ViewObject.LineColor == colors["seam-a"]
    assert second.ViewObject.LineColor == colors["seam-b"]
    assert first.ViewObject.LineColor != second.ViewObject.LineColor


def test_show_2d_does_not_select_seams_over_their_colors():
    seam = SimpleNamespace(SeamId="seam-1", ViewObject=SimpleNamespace(LineColor=None))
    piece = SimpleNamespace(PatternType="PatternPiece")

    class Selection:
        added = []
        cleared = 0

        @classmethod
        def clearSelection(cls):
            cls.cleared += 1

        @classmethod
        def addSelection(cls, obj):
            cls.added.append(obj)

    class View:
        def __init__(self):
            self.top = 0
            self.fit = 0

        def viewTop(self):
            self.top += 1

        def fitAll(self):
            self.fit += 1

    view = View()
    active = SimpleNamespace(Document=SimpleNamespace(Objects=[piece, seam]), activeView=lambda: view)
    gui = SimpleNamespace(Selection=Selection, activeDocument=lambda: active)
    previous_gui = sys.modules.get("FreeCADGui")
    sys.modules["FreeCADGui"] = gui
    try:
        show_sewing_2d()
    finally:
        if previous_gui is None:
            sys.modules.pop("FreeCADGui", None)
        else:
            sys.modules["FreeCADGui"] = previous_gui

    assert Selection.cleared == 1
    assert Selection.added == []
    assert view.top == 1
    assert view.fit == 1
