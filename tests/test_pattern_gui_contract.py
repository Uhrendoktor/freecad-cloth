# Copyright (C) 2026 FreeCAD Cloth contributors
"""Headless regression coverage for Pattern Design task-panel contracts."""

from types import SimpleNamespace

from freecad_cloth.pattern import PatternGui
from tests.support.assertions import require

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
    require(
        condition=PatternGui._is_sketch_authoritative(obj) is True,
        message="A Sketcher-authoritative piece with a linked sketch must pass.",
    )

    obj.Sketch = None
    require(
        condition=PatternGui._is_sketch_authoritative(obj) is False,
        message="A Sketcher-authoritative piece without a linked sketch must fail.",
    )


def test_sketch_authority_predicate_rejects_parameter_geometry() -> None:
    """Reject parameter-driven geometry as native Sketcher authority."""
    obj = SimpleNamespace(GeometryAuthority="PatternParameters", Sketch=object())
    require(
        condition=PatternGui._is_sketch_authoritative(obj) is False,
        message="Parameter-generated geometry must not claim Sketcher authority.",
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

    require(
        condition=(obj.Label, obj.GeometryMode) == ("Original", "Rectangle"),
        message="Reject must restore the original label and geometry mode.",
    )
    require(
        condition=(obj.Width, obj.Height)
        == (EXPECTED_ORIGINAL_WIDTH_MM, EXPECTED_ORIGINAL_HEIGHT_MM),
        message="Reject must restore the original width and height.",
    )
    require(
        condition=(obj.SeamAllowance, obj.GrainlineAngle)
        == (EXPECTED_ORIGINAL_ALLOWANCE_MM, EXPECTED_ORIGINAL_GRAINLINE_ANGLE_DEG),
        message="Reject must restore the original allowance and grainline angle.",
    )
    require(
        condition=panel.App.ActiveDocument.recompute_count == EXPECTED_RECOMPUTE_COUNT,
        message="Reject must recompute the active document exactly once.",
    )


def test_drafting_reject_restores_persisted_boundary() -> None:
    """Restore the saved drafting boundary and dimensions on task-panel rejection."""
    original_boundary = "[(0.0, 0.0), (100.0, 0.0), (80.0, 60.0)]"
    obj = SimpleNamespace(
        GeometryMode="Custom",
        DraftingBoundary=original_boundary,
        Width=EXPECTED_ORIGINAL_WIDTH_MM,
        Height=EXPECTED_ORIGINAL_HEIGHT_MM,
    )

    panel = PatternGui.PatternDraftingTaskPanel.__new__(PatternGui.PatternDraftingTaskPanel)
    panel.obj = obj
    panel.App = _App()
    panel._original = {
        "GeometryMode": "Custom",
        "DraftingBoundary": original_boundary,
        "Width": EXPECTED_ORIGINAL_WIDTH_MM,
        "Height": EXPECTED_ORIGINAL_HEIGHT_MM,
    }

    obj.GeometryMode = "Custom"
    obj.DraftingBoundary = "[(0.0, 0.0), (140.0, 0.0), (80.0, 90.0)]"
    obj.Width = 140.0
    obj.Height = 90.0
    panel.reject()

    require(
        condition=obj.GeometryMode == "Custom",
        message="Reject must restore the custom drafting mode.",
    )
    require(
        condition=obj.DraftingBoundary == original_boundary,
        message="Reject must restore the persisted drafting boundary.",
    )
    require(
        condition=(obj.Width, obj.Height)
        == (EXPECTED_ORIGINAL_WIDTH_MM, EXPECTED_ORIGINAL_HEIGHT_MM),
        message="Reject must restore the persisted drafting dimensions.",
    )
    require(
        condition=panel.App.ActiveDocument.recompute_count == EXPECTED_RECOMPUTE_COUNT,
        message="Reject must recompute the active document exactly once.",
    )


def test_drafting_editor_never_removes_last_three_points() -> None:
    """Keep at least three boundary points when removing a selected point."""
    panel = PatternGui.PatternDraftingTaskPanel.__new__(PatternGui.PatternDraftingTaskPanel)
    panel.points = [(0.0, 0.0), (100.0, 0.0), (0.0, 60.0)]
    panel.selected = 1
    original = list(panel.points)
    panel.remove_selected_point()
    require(
        condition=panel.points == original,
        message="A drafting boundary must retain all three points when removal is refused.",
    )
