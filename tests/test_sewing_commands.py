"""Headless regression coverage for the Sewing workbench command layer."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from SewingCommands import _MENU_TEXT, _SewingCommand, _selected_pattern_edges


def test_sewing_command_exposes_contextual_activation():
    state = {"active": False}
    def do_sewing(): return 17
    def active(): return state["active"]
    command = _SewingCommand(do_sewing, active, "sewing tooltip")
    assert command.IsActive() is False
    state["active"] = True
    assert command.IsActive() is True
    assert command.Activated() == 17
    assert command.GetResources() == {"MenuText": "Do Sewing", "ToolTip": "sewing tooltip"}


def test_sewing_command_accepts_explicit_public_menu_text():
    command = _SewingCommand(lambda: None, lambda: True, "tooltip", "Create M:N Sewing")
    assert command.GetResources() == {"MenuText": "Create M:N Sewing", "ToolTip": "tooltip"}


def test_all_registered_sewing_commands_have_stable_user_facing_labels():
    expected = {
        "ClothSewing_CreateSeam": "Create Seam",
        "ClothSewing_CreateMNSewing": "Create M:N Sewing",
        "ClothSewing_CreateOperation": "Create Sewing Operation",
        "ClothSewing_EditOperation": "Edit Sewing Operation",
        "ClothSewing_ReverseSeam": "Reverse Seam",
        "ClothSewing_ToggleAlignment": "Toggle Seam Alignment",
        "ClothSewing_Validate": "Validate Sewing",
        "ClothSewing_Show2D": "Show Sewing 2D",
    }
    assert _MENU_TEXT == expected


def test_selected_pattern_edges_requires_two_different_pieces(monkeypatch):
    class Selection:
        def __init__(self, selections): self._selections = selections
        def getSelectionEx(self): return self._selections
    class Piece: PatternType = "PatternPiece"
    first, second = Piece(), Piece()
    selection = type("SelectionEx", (), {"Object": first, "SubElementNames": ["Edge1"]})()
    selection_b = type("SelectionEx", (), {"Object": second, "SubElementNames": ["Edge3"]})()
    gui = type("Gui", (), {"Selection": Selection([selection, selection_b])})
    monkeypatch.setitem(sys.modules, "FreeCADGui", gui)
    assert _selected_pattern_edges() == [(first, 0), (second, 2)]


def test_selected_pattern_edges_rejects_incomplete_selection(monkeypatch):
    class Selection:
        def getSelectionEx(self): return []
    gui = type("Gui", (), {"Selection": Selection()})
    monkeypatch.setitem(sys.modules, "FreeCADGui", gui)
    try:
        _selected_pattern_edges()
    except ValueError as exc:
        assert "exactly two edges" in str(exc)
    else:
        raise AssertionError("expected invalid selection to be rejected")


def test_selected_pattern_edges_ignores_malformed_and_duplicate_subelements(monkeypatch):
    class Selection:
        def getSelectionEx(self):
            return [
                type("SelectionEx", (), {"Object": first, "SubElementNames": ["Edge0", "Edge1", "Edge1", "Face1", "Edgebad"]})(),
                type("SelectionEx", (), {"Object": second, "SubElementNames": ["Edge2"]})(),
            ]
    class Piece: PatternType = "PatternPiece"
    first, second = Piece(), Piece()
    gui = type("Gui", (), {"Selection": Selection()})
    monkeypatch.setitem(sys.modules, "FreeCADGui", gui)
    assert _selected_pattern_edges() == [(first, 0), (second, 1)]


def test_selected_pattern_edges_preserves_unique_mn_members_in_selection_order(monkeypatch):
    class Selection:
        def getSelectionEx(self):
            return [
                type("SelectionEx", (), {"Object": first, "SubElementNames": ["Edge2", "Edge4"]})(),
                type("SelectionEx", (), {"Object": second, "SubElementNames": ["Edge1", "Edge3", "Edge1"]})(),
            ]
    class Piece: PatternType = "PatternPiece"
    first, second = Piece(), Piece()
    gui = type("Gui", (), {"Selection": Selection()})
    monkeypatch.setitem(sys.modules, "FreeCADGui", gui)
    assert _selected_pattern_edges(allow_many=True) == [(first, 1), (first, 3), (second, 0), (second, 2)]
