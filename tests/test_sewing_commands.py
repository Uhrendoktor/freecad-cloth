# Copyright (C) 2026 FreeCAD Cloth contributors
"""Headless regression coverage for the Sewing workbench command layer."""

from collections.abc import Callable
from types import SimpleNamespace

import pytest

import freecad_cloth.sewing.SeamOverlay as overlay_module
import freecad_cloth.sewing.SewingCommands as sewing_commands
from freecad_cloth.sewing.SeamOverlay import (
    seam_highlights_enabled,
    seam_overlay_respects_depth,
    set_seam_highlights_enabled,
    set_seam_overlay_respect_depth,
)
from tests.support.pattern_fixtures import sketcher_pattern_piece

SEWING_ACTIVATED_RESULT = 17
FIRST_EDGE_INDEX = 0
SECOND_EDGE_INDEX = 1
THIRD_EDGE_INDEX = 2
FOURTH_EDGE_INDEX = 3
REPAIR_EDGE_LENGTH_OFFSET = 10.0

type EdgeLength = Callable[[SimpleNamespace, int], float]
type RepairContext = tuple[
    SimpleNamespace,
    SimpleNamespace,
    SimpleNamespace,
    SimpleNamespace,
    SimpleNamespace,
]


def test_sewing_command_exposes_contextual_activation() -> None:
    """Expose activation only when the command context is available."""
    state = {"active": False}

    def do_sewing() -> int:
        return SEWING_ACTIVATED_RESULT

    def active() -> bool:
        return state["active"]

    command = sewing_commands._SewingCommand(do_sewing, active, "sewing tooltip")
    assert command.IsActive() is False, "command starts inactive"
    state["active"] = True
    assert command.IsActive() is True, "active context enables command"
    assert command.Activated() == SEWING_ACTIVATED_RESULT, (
        "activation returns the sewing operation result"
    )
    resources = command.GetResources()
    assert resources["MenuText"] == "Do Sewing", "default menu text is stable"
    assert resources["ToolTip"] == "sewing tooltip", "tooltip is preserved"
    assert "Pixmap" not in resources, "missing icons are not advertised"


def test_sewing_command_accepts_explicit_public_menu_text() -> None:
    """Allow callers to set the command's public menu label."""
    command = sewing_commands._SewingCommand(
        lambda: None, lambda: True, "tooltip", "Create M:N Sewing"
    )
    resources = command.GetResources()
    assert resources["MenuText"] == "Create M:N Sewing", "custom menu text is returned"
    assert resources["ToolTip"] == "tooltip", "tooltip is preserved"
    assert "Pixmap" not in resources, "missing icons are not advertised"


def test_all_registered_sewing_commands_have_stable_user_facing_labels() -> None:
    """Keep every registered sewing command's label stable."""
    expected = {
        "ClothSewing_CreateSeam": "Create Seam",
        "ClothSewing_CreateMNSewing": "Create M:N Sewing",
        "ClothSewing_CreateOperation": "Create Sewing Operation",
        "ClothSewing_EditOperation": "Edit Sewing Operation",
        "ClothSewing_ReverseSeam": "Reverse Seam",
        "ClothSewing_ToggleAlignment": "Toggle Seam Alignment",
        "ClothSewing_Validate": "Validate Sewing",
        "ClothSewing_RepairSeam": "Repair Seam",
        "ClothSewing_Show2D": "Show Sewing 2D",
        "ClothSewing_SeamOverlayOptions": "Seam Overlay Options",
        "ClothSewing_FocusSeam3D": "Focus Seam in 3D",
        "ClothSewing_EditSeamSideA": "Edit Seam Side A in Sketcher",
        "ClothSewing_EditSeamSideB": "Edit Seam Side B in Sketcher",
    }
    assert expected == sewing_commands._MENU_TEXT, "registered command labels remain stable"


def test_seam_overlay_labels_are_limited_to_the_hovered_seam() -> None:
    """Show a label only for the currently hovered seam."""
    assert overlay_module.should_show_seam_label("seam-1", "seam-1"), (
        "hovered seam label is visible"
    )
    assert not overlay_module.should_show_seam_label("seam-1", ""), (
        "empty hover target hides the label"
    )
    assert not overlay_module.should_show_seam_label("seam-1", "seam-2"), (
        "another seam's label remains hidden"
    )


def test_seam_overlay_preferences_can_be_changed_and_restored() -> None:
    """Change overlay preferences and restore their original values."""
    original_highlights = seam_highlights_enabled()
    original_depth = seam_overlay_respects_depth()
    try:
        assert set_seam_highlights_enabled(not original_highlights) is not original_highlights, (
            "highlight preference setter returns its applied value"
        )
        assert seam_highlights_enabled() is not original_highlights, (
            "highlight preference can be toggled"
        )
        assert set_seam_overlay_respect_depth(not original_depth) is not original_depth, (
            "depth preference setter returns its applied value"
        )
        assert seam_overlay_respects_depth() is not original_depth, (
            "depth preference can be toggled"
        )
    finally:
        set_seam_highlights_enabled(original_highlights)
        set_seam_overlay_respect_depth(original_depth)


def test_selected_pattern_edges_requires_two_different_pieces() -> None:
    """Require an edge selection from two distinct pattern pieces."""
    first = SimpleNamespace(PatternType="PatternPiece")
    second = SimpleNamespace(PatternType="PatternPiece")
    selection_a = SimpleNamespace(Object=first, SubElementNames=["Edge1"])
    selection_b = SimpleNamespace(Object=second, SubElementNames=["Edge3"])
    gui = SimpleNamespace(
        Selection=SimpleNamespace(getSelectionEx=lambda: [selection_a, selection_b])
    )
    assert sewing_commands._selected_pattern_edges(gui=gui) == [
        (first, FIRST_EDGE_INDEX),
        (second, THIRD_EDGE_INDEX),
    ], "selected edges retain their piece and zero-based index"


def test_selected_pattern_edges_rejects_incomplete_selection() -> None:
    """Reject selections that do not contain exactly two valid edges."""
    gui = SimpleNamespace(Selection=SimpleNamespace(getSelectionEx=list))
    with pytest.raises(ValueError, match="exactly two edges"):
        sewing_commands._selected_pattern_edges(gui=gui)


def test_selected_pattern_edges_ignores_malformed_and_duplicate_subelements() -> None:
    """Ignore malformed or duplicate edge subelements."""
    first = SimpleNamespace(PatternType="PatternPiece")
    second = SimpleNamespace(PatternType="PatternPiece")
    selection_a = SimpleNamespace(
        Object=first,
        SubElementNames=["Edge0", "Edge1", "Edge1", "Face1", "Edgebad"],
    )
    selection_b = SimpleNamespace(Object=second, SubElementNames=["Edge2"])
    gui = SimpleNamespace(
        Selection=SimpleNamespace(getSelectionEx=lambda: [selection_a, selection_b])
    )
    assert sewing_commands._selected_pattern_edges(gui=gui) == [
        (first, FIRST_EDGE_INDEX),
        (second, SECOND_EDGE_INDEX),
    ], "only unique, valid edge names are retained"


def test_selected_pattern_edges_preserves_unique_mn_members_in_selection_order() -> None:
    """Preserve unique M:N edge members in selection order."""
    first = SimpleNamespace(PatternType="PatternPiece")
    second = SimpleNamespace(PatternType="PatternPiece")
    selection_a = SimpleNamespace(Object=first, SubElementNames=["Edge2", "Edge4"])
    selection_b = SimpleNamespace(Object=second, SubElementNames=["Edge1", "Edge3", "Edge1"])
    gui = SimpleNamespace(
        Selection=SimpleNamespace(getSelectionEx=lambda: [selection_a, selection_b])
    )
    assert sewing_commands._selected_pattern_edges(allow_many=True, gui=gui) == [
        (first, SECOND_EDGE_INDEX),
        (first, FOURTH_EDGE_INDEX),
        (second, FIRST_EDGE_INDEX),
        (second, THIRD_EDGE_INDEX),
    ], "M:N edges retain selection and edge order while removing duplicates"


def _repair_test_modules(
    pieces: tuple[SimpleNamespace, ...] = (),
) -> RepairContext:
    """Build isolated seam-repair collaborators for deterministic command tests."""
    seam = SimpleNamespace(
        SeamId="seam-1",
        PieceA="piece-a",
        PieceB="piece-b",
        EdgeA=FIRST_EDGE_INDEX,
        EdgeB=SECOND_EDGE_INDEX,
        EdgeAId="piece-a:edge:0",
        EdgeBId="piece-b:edge:1",
        EdgeASignature="stale-a",
        EdgeBSignature="stale-b",
        LengthA=0.0,
        LengthB=0.0,
    )
    gui = SimpleNamespace(Selection=SimpleNamespace(getSelection=lambda: [seam]))
    doc = SimpleNamespace(Objects=[seam, *pieces], recompute=lambda: None)
    app = SimpleNamespace(ActiveDocument=doc)
    services = SimpleNamespace(
        correspondence_report=lambda *_args: {"status": "ok"},
        repair_correspondence_settings=lambda *_args: "repaired",
    )
    return seam, doc, app, gui, services


def _run_repair(context: RepairContext, edge_length: EdgeLength) -> str:
    """Run repair against the supplied fake GUI, document, and seam collaborators."""
    _seam, _doc, app, gui, services = context
    return sewing_commands.repair_selected_seam(
        app=app,
        gui=gui,
        edge_length_fn=edge_length,
        correspondence_report_fn=services.correspondence_report,
        repair_settings_fn=services.repair_correspondence_settings,
    )


def _pattern_piece(piece_id: str) -> SimpleNamespace:
    """Build a minimal valid pattern piece with a square sewing outline."""
    return sketcher_pattern_piece(
        piece_id,
        ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)),
    )


def test_repair_selected_seam_wraps_missing_piece_with_actionable_context() -> None:
    """Report missing pattern pieces with actionable repair context."""

    def edge_length(_piece: SimpleNamespace, _edge: int) -> float:
        msg = "edge lookup must not run when the piece is missing"
        raise AssertionError(msg)

    context = _repair_test_modules()
    with pytest.raises(ValueError, match="cannot determine seam lengths for repair") as exc_info:
        _run_repair(context, edge_length)
    assert "piece-a" in str(exc_info.value), "repair error names the missing piece"
    assert isinstance(exc_info.value.__cause__, KeyError), (
        "repair error preserves the missing-piece cause"
    )


def test_repair_selected_seam_wraps_invalid_edge_without_losing_cause() -> None:
    """Preserve the invalid edge failure as a repair exception cause."""

    def edge_length(_piece: SimpleNamespace, edge: int) -> float:
        msg = f"seam edge {edge} is outside the pattern boundary"
        raise ValueError(msg)

    pieces = (_pattern_piece("piece-a"), _pattern_piece("piece-b"))
    context = _repair_test_modules(pieces)
    with pytest.raises(ValueError, match="outside the pattern boundary") as exc_info:
        _run_repair(context, edge_length)
    assert isinstance(exc_info.value.__cause__, ValueError), (
        "repair error preserves the invalid-edge cause"
    )


def test_repair_selected_seam_does_not_swallow_unexpected_runtime_error() -> None:
    """Propagate unexpected runtime errors instead of swallowing them."""

    def edge_length(_piece: SimpleNamespace, _edge: int) -> float:
        msg = "unexpected solver/runtime failure"
        raise RuntimeError(msg)

    pieces = (_pattern_piece("piece-a"), _pattern_piece("piece-b"))
    context = _repair_test_modules(pieces)
    with pytest.raises(RuntimeError, match="unexpected solver/runtime failure"):
        _run_repair(context, edge_length)


def test_repair_selected_seam_successful_repair_refreshes_existing_semantic_edges() -> None:
    """Refresh stable semantic edge identifiers after successful repair."""

    def edge_length(_piece: SimpleNamespace, edge: int) -> float:
        return REPAIR_EDGE_LENGTH_OFFSET + edge

    pieces = (_pattern_piece("piece-a"), _pattern_piece("piece-b"))
    context = _repair_test_modules(pieces)
    assert _run_repair(context, edge_length) == "repaired", "repair reports success"
    seam = context[0]
    assert seam.EdgeAId == "piece-a:edge:0", "edge A identity is preserved"
    assert seam.EdgeBId == "piece-b:edge:1", "edge B identity is preserved"
    assert seam.EdgeASignature != "stale-a", "edge A signature is refreshed"
    assert seam.EdgeBSignature != "stale-b", "edge B signature is refreshed"


def test_edit_selected_seam_side_selects_authoritative_sketch_before_editing() -> None:
    """Select the authoritative sketch and edge before entering Sketcher edit mode."""
    active_document = SimpleNamespace(calls=[])
    selection = SimpleNamespace(calls=[])
    piece = SimpleNamespace(PieceId="piece-a", PatternType="PatternPiece")
    sketch = SimpleNamespace(Name="Sketch")
    piece.Sketch = sketch
    sketch.SemanticEdgeIds = (
        "piece-a:edge:0",
        "piece-a:edge:1",
        "piece-a:edge:2",
    )
    seam = SimpleNamespace(
        SeamId="seam-1",
        PatternA=piece,
        PatternB=piece,
        EdgeAId="piece-a:edge:2",
        EdgeBId="piece-a:edge:3",
    )
    selection.getSelection = lambda: [seam]
    selection.clearSelection = lambda: selection.calls.append(("clear",))
    selection.addSelection = lambda obj, sub_name=None: selection.calls.append(
        ("add", obj, sub_name)
    )
    active_document.getInEdit = lambda: active_document.calls.append(("getInEdit",)) or True
    active_document.resetEdit = lambda: active_document.calls.append(("resetEdit",))
    active_document.setEdit = lambda name: active_document.calls.append(("setEdit", name))
    gui = SimpleNamespace(
        Selection=selection,
        activeDocument=lambda: active_document,
        activateWorkbench=lambda name: active_document.calls.append(("activateWorkbench", name)),
    )
    app = SimpleNamespace(ActiveDocument=active_document)

    edited_sketch, edge_index = sewing_commands.edit_selected_seam_side_a(
        app=app, gui=gui, focus_fn=lambda: None
    )
    assert edited_sketch is sketch, "authoritative sketch is returned"
    assert edge_index == THIRD_EDGE_INDEX, "semantic edge index is preserved"
    assert active_document.calls == [
        ("getInEdit",),
        ("resetEdit",),
        ("activateWorkbench", "SketcherWorkbench"),
        ("setEdit", "Sketch"),
    ], "document enters Sketcher edit mode in order"
    assert selection.calls == [
        ("clear",),
        ("add", piece, None),
        ("clear",),
        ("add", sketch, "Edge3"),
    ], "selection transitions from the piece to its authoritative sketch edge"
