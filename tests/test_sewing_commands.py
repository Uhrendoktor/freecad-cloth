"""Headless regression coverage for the Sewing workbench command layer."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from SewingCommands import _SewingCommand, _selected_pattern_edges


def test_sewing_command_exposes_contextual_activation():
    state = {"active": False}

    def do_sewing():
        return 17

    def active():
        return state["active"]

    command = _SewingCommand(do_sewing, active, "sewing tooltip")
    assert command.IsActive() is False
    state["active"] = True
    assert command.IsActive() is True
    assert command.Activated() == 17
    assert command.GetResources() == {
        "MenuText": "Do Sewing",
        "ToolTip": "sewing tooltip",
    }


def test_selected_pattern_edges_requires_two_different_pieces(monkeypatch):
    class Selection:
        def __init__(self, selections):
            self._selections = selections

        def getSelectionEx(self):
            return self._selections

    class Piece:
        PatternType = "PatternPiece"

    first = Piece()
    second = Piece()
    selection = type("SelectionEx", (), {"Object": first, "SubElementNames": ["Edge1"]})()
    selection_b = type("SelectionEx", (), {"Object": second, "SubElementNames": ["Edge3"]})()
    gui = type("Gui", (), {"Selection": Selection([selection, selection_b])})
    monkeypatch.setitem(sys.modules, "FreeCADGui", gui)

    edges = _selected_pattern_edges()
    assert edges == [(first, 0), (second, 2)]


def test_selected_pattern_edges_rejects_incomplete_selection(monkeypatch):
    class Selection:
        def getSelectionEx(self):
            return []

    gui = type("Gui", (), {"Selection": Selection()})
    monkeypatch.setitem(sys.modules, "FreeCADGui", gui)

    try:
        _selected_pattern_edges()
    except ValueError as exc:
        assert "exactly two edges" in str(exc)
    else:
        raise AssertionError("expected invalid selection to be rejected")
