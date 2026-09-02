"""Headless regression coverage for Pattern Design task-panel contracts."""
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PatternGui = importlib.import_module("freecad_cloth.pattern.PatternGui")


class _Document:
    def __init__(self):
        self.recompute_count = 0

    def recompute(self):
        self.recompute_count += 1


class _App:
    def __init__(self):
        self.ActiveDocument = _Document()


def test_pattern_piece_reject_restores_original_properties():
    obj = type("Pattern", (), {})()
    obj.Label = "Original"
    obj.GeometryMode = "Rectangle"
    obj.Width = 100.0
    obj.Height = 60.0
    obj.SeamAllowance = 4.0
    obj.GrainlineAngle = 15.0

    panel = PatternGui.PatternPieceTaskPanel.__new__(PatternGui.PatternPieceTaskPanel)
    panel.obj = obj
    panel.App = _App()
    panel._original = {
        "Label": "Original",
        "GeometryMode": "Rectangle",
        "Width": 100.0,
        "Height": 60.0,
        "SeamAllowance": 4.0,
        "GrainlineAngle": 15.0,
    }

    obj.Label = "Edited"
    obj.GeometryMode = "Custom"
    obj.Width = 180.0
    obj.Height = 120.0
    obj.SeamAllowance = 9.0
    obj.GrainlineAngle = -30.0
    panel.reject()

    assert (obj.Label, obj.GeometryMode) == ("Original", "Rectangle")
    assert (obj.Width, obj.Height) == (100.0, 60.0)
    assert (obj.SeamAllowance, obj.GrainlineAngle) == (4.0, 15.0)
    assert panel.App.ActiveDocument.recompute_count == 1


def test_drafting_reject_restores_persisted_boundary():
    obj = type("Pattern", (), {})()
    obj.GeometryMode = "Custom"
    obj.DraftingBoundary = "[(0.0, 0.0), (100.0, 0.0), (80.0, 60.0)]"
    obj.Width = 100.0
    obj.Height = 60.0

    panel = PatternGui.PatternDraftingTaskPanel.__new__(PatternGui.PatternDraftingTaskPanel)
    panel.obj = obj
    panel.App = _App()
    panel._original = {
        "GeometryMode": "Custom",
        "DraftingBoundary": obj.DraftingBoundary,
        "Width": 100.0,
        "Height": 60.0,
    }

    obj.GeometryMode = "Custom"
    obj.DraftingBoundary = "[(0.0, 0.0), (140.0, 0.0), (80.0, 90.0)]"
    obj.Width = 140.0
    obj.Height = 90.0
    panel.reject()

    assert obj.GeometryMode == "Custom"
    assert obj.DraftingBoundary == "[(0.0, 0.0), (100.0, 0.0), (80.0, 60.0)]"
    assert (obj.Width, obj.Height) == (100.0, 60.0)
    assert panel.App.ActiveDocument.recompute_count == 1


def test_drafting_editor_never_removes_last_three_points():
    panel = PatternGui.PatternDraftingTaskPanel.__new__(PatternGui.PatternDraftingTaskPanel)
    panel.points = [(0.0, 0.0), (100.0, 0.0), (0.0, 60.0)]
    panel.selected = 1
    original = list(panel.points)
    panel.remove_selected_point()
    assert panel.points == original
