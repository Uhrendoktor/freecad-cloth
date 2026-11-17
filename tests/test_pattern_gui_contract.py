# Copyright (C) 2026 FreeCAD Cloth contributors
"""Headless regression coverage for Pattern Design task-panel contracts."""

from types import SimpleNamespace

from freecad_cloth.pattern import PatternExportGui, PatternGui

EXPECTED_RECOMPUTE_COUNT = 1
EXPECTED_ORIGINAL_WIDTH_MM = 100.0
EXPECTED_ORIGINAL_HEIGHT_MM = 60.0
EXPECTED_ORIGINAL_ALLOWANCE_MM = 4.0
EXPECTED_ORIGINAL_GRAINLINE_ANGLE_DEG = 15.0


class _Document:
    """Minimal document double that records recomputation requests."""

    def __init__(self) -> None:
        """Initialize the recomputation counter."""
        self.recompute_count: int = 0

    def recompute(self) -> None:
        """Record one document recomputation requested by a task panel."""
        self.recompute_count += 1


class _App:
    """Minimal application double exposing an active document."""

    def __init__(self) -> None:
        """Create the active-document fixture."""
        self.ActiveDocument: _Document = _Document()


def test_sketch_authority_predicate_requires_linked_sketch() -> None:
    """Require a native Sketcher link before declaring a pattern authoritative."""
    obj = SimpleNamespace(GeometryAuthority="Sketcher", Sketch=object())
    assert PatternGui._is_sketch_authoritative(obj) is True, (
        "A Sketcher-authoritative piece with a linked sketch must pass."
    )

    obj.Sketch = None
    assert PatternGui._is_sketch_authoritative(obj) is False, (
        "A Sketcher-authoritative piece without a linked sketch must fail."
    )


def test_sketch_authority_predicate_rejects_parameter_geometry() -> None:
    """Reject parameter-driven geometry as native Sketcher authority."""
    obj = SimpleNamespace(GeometryAuthority="PatternParameters", Sketch=object())
    assert PatternGui._is_sketch_authoritative(obj) is False, (
        "Parameter-generated geometry must not claim Sketcher authority."
    )


def test_pattern_piece_reject_restores_original_properties() -> None:
    """Restore saved piece values and recompute the document on task-panel rejection."""
    obj = SimpleNamespace(
        Label="Original",
        GeometryMode="Rectangle",
        Width=EXPECTED_ORIGINAL_WIDTH_MM,
        Height=EXPECTED_ORIGINAL_HEIGHT_MM,
        SeamAllowance=EXPECTED_ORIGINAL_ALLOWANCE_MM,
        GrainlineAngle=EXPECTED_ORIGINAL_GRAINLINE_ANGLE_DEG,
    )

    panel = PatternGui.PatternPieceTaskPanel.__new__(PatternGui.PatternPieceTaskPanel)
    panel.obj = obj
    panel.App = _App()
    panel._original = {
        "Label": "Original",
        "GeometryMode": "Rectangle",
        "Width": EXPECTED_ORIGINAL_WIDTH_MM,
        "Height": EXPECTED_ORIGINAL_HEIGHT_MM,
        "SeamAllowance": EXPECTED_ORIGINAL_ALLOWANCE_MM,
        "GrainlineAngle": EXPECTED_ORIGINAL_GRAINLINE_ANGLE_DEG,
    }

    obj.Label = "Edited"
    obj.GeometryMode = "Custom"
    obj.Width = 180.0
    obj.Height = 120.0
    obj.SeamAllowance = 9.0
    obj.GrainlineAngle = -30.0
    panel.reject()

    assert (obj.Label, obj.GeometryMode) == ("Original", "Rectangle"), (
        "Reject must restore the original label and geometry mode."
    )
    assert (obj.Width, obj.Height) == (EXPECTED_ORIGINAL_WIDTH_MM, EXPECTED_ORIGINAL_HEIGHT_MM), (
        "Reject must restore the original width and height."
    )
    assert (obj.SeamAllowance, obj.GrainlineAngle) == (
        EXPECTED_ORIGINAL_ALLOWANCE_MM,
        EXPECTED_ORIGINAL_GRAINLINE_ANGLE_DEG,
    ), "Reject must restore the original allowance and grainline angle."
    assert panel.App.ActiveDocument.recompute_count == EXPECTED_RECOMPUTE_COUNT, (
        "Reject must recompute the active document exactly once."
    )


def test_sketch_edit_uses_the_linked_native_sketch() -> None:
    """Enter Sketcher editing through the persisted native sketch object."""
    sketch = SimpleNamespace(Name="AuthoritativeSketch")
    calls: list[str] = []
    active_document = SimpleNamespace(setEdit=calls.append)
    panel = PatternGui.PatternPieceTaskPanel.__new__(PatternGui.PatternPieceTaskPanel)
    panel._sketch_authoritative = True
    panel.obj = SimpleNamespace(Sketch=sketch)
    panel.Gui = SimpleNamespace(activeDocument=lambda: active_document)

    panel._edit_sketch()

    assert calls == ["AuthoritativeSketch"], "Sketch edit must target the linked native sketch."


def test_sketch_authoritative_mode_displays_read_only_sketch_dimensions() -> None:
    """Label dimensions as Sketch-derived and keep them visible but non-editable."""
    width_states: list[bool] = []
    height_states: list[bool] = []
    visible_states: list[bool] = []
    width_tooltips: list[str] = []
    height_tooltips: list[str] = []
    width_label: list[str] = []
    height_label: list[str] = []
    panel = PatternGui.PatternPieceTaskPanel.__new__(PatternGui.PatternPieceTaskPanel)
    panel._sketch_authoritative = True
    panel.width = SimpleNamespace(
        setEnabled=width_states.append,
        setVisible=visible_states.append,
        setToolTip=width_tooltips.append,
    )
    panel.height = SimpleNamespace(
        setEnabled=height_states.append,
        setVisible=visible_states.append,
        setToolTip=height_tooltips.append,
    )
    panel._width_label = SimpleNamespace(
        setText=width_label.append,
        setVisible=visible_states.append,
    )
    panel._height_label = SimpleNamespace(
        setText=height_label.append,
        setVisible=visible_states.append,
    )

    panel._mode_changed("Rectangle")

    assert width_states == [False], "Sketch authority must disable the width field."
    assert height_states == [False], "Sketch authority must disable the height field."
    assert width_label == ["Width (from Sketch)"]
    assert height_label == ["Height (from Sketch)"]
    assert visible_states == [True, True, True, True]
    assert "linked native Sketch" in width_tooltips[0]
    assert "linked native Sketch" in height_tooltips[0]


def test_pattern_piece_displays_custom_outline_dimensions_as_read_only() -> None:
    """Keep bounding dimensions visible but non-editable for a custom outline."""
    width_enabled: list[bool] = []
    height_enabled: list[bool] = []
    width_visible: list[bool] = []
    height_visible: list[bool] = []
    width_label_text: list[str] = []
    height_label_text: list[str] = []
    width_label_visible: list[bool] = []
    height_label_visible: list[bool] = []
    width_tooltips: list[str] = []
    height_tooltips: list[str] = []
    panel = PatternGui.PatternPieceTaskPanel.__new__(PatternGui.PatternPieceTaskPanel)
    panel._sketch_authoritative = False
    panel.width = SimpleNamespace(
        setEnabled=width_enabled.append,
        setVisible=width_visible.append,
        setToolTip=width_tooltips.append,
    )
    panel.height = SimpleNamespace(
        setEnabled=height_enabled.append,
        setVisible=height_visible.append,
        setToolTip=height_tooltips.append,
    )
    panel._width_label = SimpleNamespace(
        setText=width_label_text.append,
        setVisible=width_label_visible.append,
    )
    panel._height_label = SimpleNamespace(
        setText=height_label_text.append,
        setVisible=height_label_visible.append,
    )

    panel._mode_changed("Rectangle")
    assert width_enabled[-1] is True
    assert height_enabled[-1] is True
    assert width_visible[-1] is True
    assert height_visible[-1] is True
    assert width_label_text[-1] == "Width"
    assert height_label_text[-1] == "Height"

    panel._mode_changed("Custom")
    assert width_enabled[-1] is False
    assert height_enabled[-1] is False
    assert width_visible[-1] is True
    assert height_visible[-1] is True
    assert width_label_visible[-1] is True
    assert height_label_visible[-1] is True
    assert width_label_text[-1] == "Width (from outline)"
    assert height_label_text[-1] == "Height (from outline)"
    assert "derived from the custom drafting outline" in width_tooltips[-1]
    assert "derived from the custom drafting outline" in height_tooltips[-1]


def _pattern_piece_viewport_fixture(
    piece: SimpleNamespace,
) -> tuple[
    PatternGui.PatternPieceTaskPanel,
    list[tuple[str | SimpleNamespace | bool, ...]],
    SimpleNamespace,
    SimpleNamespace,
]:
    calls: list[tuple[str | SimpleNamespace | bool, ...]] = []
    view = SimpleNamespace(
        viewTop=lambda: calls.append(("top",)),
        fitAll=lambda: calls.append(("fit",)),
    )
    selection = SimpleNamespace(
        clearSelection=lambda: calls.append(("clear",)),
        addSelection=lambda obj: calls.append(("select", obj)),
    )
    panel = PatternGui.PatternPieceTaskPanel.__new__(PatternGui.PatternPieceTaskPanel)
    panel.Gui = SimpleNamespace(
        activeDocument=lambda: SimpleNamespace(activeView=lambda: view),
        Selection=selection,
    )
    return panel, calls, view, selection


def test_pattern_piece_focus_action_selects_and_frames_only_on_request() -> None:
    """Keep viewport camera changes behind the explicit task-panel action."""
    piece = SimpleNamespace(Name="FrontPiece", Label="Front")
    panel, calls, _, _ = _pattern_piece_viewport_fixture(piece)
    panel.obj = piece

    assert panel._focus_piece() is True

    assert calls == [("clear",), ("select", piece), ("top",), ("fit",)]


def test_new_pattern_piece_is_framed_once_after_creation() -> None:
    """Keep initial viewport discovery for newly created pieces behind the OK action."""
    from unittest.mock import patch

    piece = SimpleNamespace(Label="PatternPiece")
    panel, calls, view, selection = _pattern_piece_viewport_fixture(piece)
    panel.obj = None
    panel._sketch_authoritative = False
    panel.name = SimpleNamespace(text=lambda: "New front")
    panel.mode = SimpleNamespace(currentText=lambda: "Rectangle")
    panel.width = SimpleNamespace(value=lambda: 140.0)
    panel.height = SimpleNamespace(value=lambda: 85.0)
    panel.allowance = SimpleNamespace(value=lambda: 4.0)
    panel.grain = SimpleNamespace(value=lambda: 12.0)
    panel.App = _App()
    panel.Gui = SimpleNamespace(
        activeDocument=lambda: SimpleNamespace(activeView=lambda: view),
        Selection=selection,
    )
    panel.focus_piece = SimpleNamespace(setEnabled=lambda value: calls.append(("enabled", value)))

    with patch(
        "freecad_cloth.pattern.PatternCommands.create_pattern_piece_from_parameters",
        return_value=piece,
    ) as create:
        panel._apply()

    create.assert_called_once_with("New front", 140.0, 85.0, 4.0, 12.0)
    assert piece.Label == "New front"
    assert calls == [
        ("enabled", True),
        ("clear",),
        ("select", piece),
        ("top",),
        ("fit",),
    ]


def test_pattern_piece_apply_does_not_change_viewport_camera() -> None:
    """Applying piece properties must not silently change the current camera."""
    piece = SimpleNamespace(
        Label="Front",
        GeometryMode="Rectangle",
        Width=100.0,
        Height=60.0,
        SeamAllowance=4.0,
        GrainlineAngle=15.0,
    )
    focus_enabled: list[bool] = []
    viewport_calls: list[str] = []
    panel = PatternGui.PatternPieceTaskPanel.__new__(PatternGui.PatternPieceTaskPanel)
    panel.obj = piece
    panel._sketch_authoritative = False
    panel.name = SimpleNamespace(text=lambda: "Front edited")
    panel.mode = SimpleNamespace(currentText=lambda: "Rectangle")
    panel.width = SimpleNamespace(value=lambda: 120.0)
    panel.height = SimpleNamespace(value=lambda: 70.0)
    panel.allowance = SimpleNamespace(value=lambda: 5.0)
    panel.grain = SimpleNamespace(value=lambda: 20.0)
    panel.App = _App()
    panel.Gui = SimpleNamespace(
        activeDocument=lambda: SimpleNamespace(
            activeView=lambda: SimpleNamespace(
                viewTop=lambda: viewport_calls.append("top"),
                fitAll=lambda: viewport_calls.append("fit"),
            )
        )
    )
    panel.focus_piece = SimpleNamespace(setEnabled=focus_enabled.append)

    panel._apply()

    assert piece.Label == "Front edited"
    assert (piece.Width, piece.Height, piece.SeamAllowance, piece.GrainlineAngle) == (
        120.0,
        70.0,
        5.0,
        20.0,
    )
    assert panel.App.ActiveDocument.recompute_count == EXPECTED_RECOMPUTE_COUNT
    assert focus_enabled == [True]
    assert viewport_calls == [], "Property application must leave the current camera unchanged."


def test_reject_restores_properties_without_replacing_sketch_identity() -> None:
    """Restore editable properties while preserving the linked Sketcher object."""
    sketch = SimpleNamespace(Name="AuthoritativeSketch")
    obj = SimpleNamespace(
        Label="Original",
        GeometryMode="Sketch",
        Width=EXPECTED_ORIGINAL_WIDTH_MM,
        Height=EXPECTED_ORIGINAL_HEIGHT_MM,
        SeamAllowance=EXPECTED_ORIGINAL_ALLOWANCE_MM,
        GrainlineAngle=EXPECTED_ORIGINAL_GRAINLINE_ANGLE_DEG,
        Sketch=sketch,
    )
    panel = PatternGui.PatternPieceTaskPanel.__new__(PatternGui.PatternPieceTaskPanel)
    panel.obj = obj
    panel.App = _App()
    panel._original = {
        "Label": "Original",
        "GeometryMode": "Sketch",
        "Width": EXPECTED_ORIGINAL_WIDTH_MM,
        "Height": EXPECTED_ORIGINAL_HEIGHT_MM,
        "SeamAllowance": EXPECTED_ORIGINAL_ALLOWANCE_MM,
        "GrainlineAngle": EXPECTED_ORIGINAL_GRAINLINE_ANGLE_DEG,
    }
    obj.Label = "Edited"
    obj.SeamAllowance = 9.0
    obj.GrainlineAngle = -30.0

    panel.reject()

    assert obj.Sketch is sketch, "Reject must preserve the linked native sketch identity."
    assert obj.Label == "Original", "Reject must restore the original pattern-piece label."
    assert obj.SeamAllowance == EXPECTED_ORIGINAL_ALLOWANCE_MM
    assert obj.GrainlineAngle == EXPECTED_ORIGINAL_GRAINLINE_ANGLE_DEG
    assert panel.App.ActiveDocument.recompute_count == EXPECTED_RECOMPUTE_COUNT


def test_pattern_export_focus_action_selects_and_frames_source_without_changing_camera() -> None:
    """Expose a source-focus action while preserving the current viewport orientation."""
    piece = SimpleNamespace(Name="FrontPiece")
    calls: list[tuple[str | SimpleNamespace | bool, ...]] = []
    view = SimpleNamespace(fitAll=lambda: calls.append(("fit",)))
    selection = SimpleNamespace(
        clearSelection=lambda: calls.append(("clear",)),
        addSelection=lambda obj: calls.append(("select", obj)),
    )
    panel = PatternExportGui.PatternExportTaskPanel.__new__(PatternExportGui.PatternExportTaskPanel)
    panel.piece = piece
    panel.App = SimpleNamespace(ActiveDocument=object())
    panel.Gui = SimpleNamespace(
        activeDocument=lambda: SimpleNamespace(activeView=lambda: view),
        Selection=selection,
    )

    assert panel.focus_source_in_3d() is True
    assert calls == [("clear",), ("select", piece), ("fit",)]
