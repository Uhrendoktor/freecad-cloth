# Copyright (C) 2026 FreeCAD Cloth contributors
"""Headless regression coverage for Pattern Design task-panel contracts."""

from types import SimpleNamespace

from freecad_cloth.pattern import PatternGui

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


def test_sketch_authoritative_mode_disables_parameter_geometry_controls() -> None:
    """Keep dimensions non-editable when the native sketch owns the boundary."""
    width_states: list[bool] = []
    height_states: list[bool] = []
    panel = PatternGui.PatternPieceTaskPanel.__new__(PatternGui.PatternPieceTaskPanel)
    panel._sketch_authoritative = True
    panel.width = SimpleNamespace(setEnabled=width_states.append)
    panel.height = SimpleNamespace(setEnabled=height_states.append)

    panel._mode_changed("Rectangle")

    assert width_states == [False], "Sketch authority must disable the width field."
    assert height_states == [False], "Sketch authority must disable the height field."


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
