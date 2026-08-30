"""Headless regression coverage for the Sewing workbench command layer."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from SewingCommands import _MENU_TEXT, _SewingCommand, _selected_pattern_edges, repair_selected_seam


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


def _repair_test_modules(monkeypatch, edge_length):
    class Seam:
        SeamId = "seam-1"
        PieceA = "missing-a"
        PieceB = "missing-b"
        EdgeA = 0
        EdgeB = 1
        LengthA = 0.0
        LengthB = 0.0

    seam = Seam()
    class Selection:
        def getSelection(self): return [seam]

    class Gui:
        Selection = Selection()

    class App:
        class Document:
            Objects = [seam]
            def recompute(self): pass
        ActiveDocument = Document()

    sewing_gui = type("SewingGui", (), {
        "correspondence_report": staticmethod(lambda *args: {"status": "ok"}),
        "repair_correspondence_settings": staticmethod(lambda *args: "repaired"),
    })
    sewing_objects = type("SewingObjects", (), {"_edge_length": staticmethod(edge_length)})
    monkeypatch.setitem(sys.modules, "FreeCADGui", Gui)
    monkeypatch.setitem(sys.modules, "FreeCAD", App)
    monkeypatch.setitem(sys.modules, "SewingGui", sewing_gui)
    monkeypatch.setitem(sys.modules, "SewingObjects", sewing_objects)
    return seam


def test_repair_selected_seam_wraps_missing_piece_with_actionable_context(monkeypatch):
    def edge_length(_piece, _edge):
        raise AssertionError("edge lookup must not run when the piece is missing")

    _repair_test_modules(monkeypatch, edge_length)
    import SewingCommands
    try:
        SewingCommands.repair_selected_seam()
    except ValueError as exc:
        assert "cannot determine seam lengths for repair" in str(exc)
        assert "missing-a" in str(exc)
        assert isinstance(exc.__cause__, KeyError)
    else:
        raise AssertionError("expected missing pattern pieces to be reported")


def test_repair_selected_seam_wraps_invalid_edge_without_losing_cause(monkeypatch):
    def edge_length(_piece, edge):
        raise ValueError(f"seam edge {edge} is outside the pattern boundary")

    seam = _repair_test_modules(monkeypatch, edge_length)
    class Piece:
        PieceId = "missing-a"
    seam_doc = sys.modules["FreeCAD"].ActiveDocument
    seam_doc.Objects = [seam, Piece()]
    try:
        repair_selected_seam()
    except ValueError as exc:
        assert "outside the pattern boundary" in str(exc)
        assert isinstance(exc.__cause__, ValueError)
    else:
        raise AssertionError("expected invalid seam edge to be reported")


def test_repair_selected_seam_does_not_swallow_unexpected_runtime_error(monkeypatch):
    def edge_length(_piece, _edge):
        raise RuntimeError("unexpected solver/runtime failure")

    seam = _repair_test_modules(monkeypatch, edge_length)
    class Piece:
        PieceId = "missing-a"
    seam_doc = sys.modules["FreeCAD"].ActiveDocument
    seam_doc.Objects = [seam, Piece()]
    try:
        repair_selected_seam()
    except RuntimeError as exc:
        assert str(exc) == "unexpected solver/runtime failure"
    else:
        raise AssertionError("unexpected runtime errors must not be swallowed")


def test_repair_selected_seam_successful_repair_keeps_public_result(monkeypatch):
    def edge_length(_piece, edge):
        return 10.0 + edge

    seam = _repair_test_modules(monkeypatch, edge_length)
    class PieceA:
        PieceId = "missing-a"
    class PieceB:
        PieceId = "missing-b"
    seam_doc = sys.modules["FreeCAD"].ActiveDocument
    seam_doc.Objects = [seam, PieceA(), PieceB()]
    assert repair_selected_seam() == "repaired"
