# Copyright (C) 2026 FreeCAD Cloth contributors
"""Headless contracts for viewport-driven semantic topology repair."""

from types import SimpleNamespace
from unittest.mock import patch

from freecad_cloth.pattern.PatternTopologyRepairGui import _TopologyRepairViewportPicker


class _Selection:
    """Capture FreeCAD selection-observer registration and removal."""

    def __init__(self) -> None:
        self.observers: list[object] = []

    def addObserver(self, observer: object) -> None:
        self.observers.append(observer)

    def removeObserver(self, observer: object) -> None:
        self.observers.remove(observer)


class _Combo:
    """Represent a row's semantic edge combo box."""

    def __init__(self, records: tuple[str, ...]) -> None:
        self.items = records
        self.current_index = 0

    def findData(self, value: str) -> int:
        try:
            return self.items.index(value)
        except ValueError:
            return -1

    def setCurrentIndex(self, index: int) -> None:
        self.current_index = int(index)


class _VisibilityButton:
    """Capture the Cancel-pick visibility state."""

    def __init__(self) -> None:
        self.visible = False

    def setVisible(self, visible: bool) -> None:
        self.visible = bool(visible)


def _picker_fixture():
    """Build one seam-side picker with isolated document, selection and feedback."""
    document = SimpleNamespace(Name="ClothDocument")
    front_sketch = SimpleNamespace(
        Name="FrontSketch",
        Label="Front native Sketch",
        Document=document,
        ViewObject=SimpleNamespace(Visibility=False),
    )
    back_sketch = SimpleNamespace(
        Name="BackSketch",
        Label="Back native Sketch",
        Document=document,
        ViewObject=SimpleNamespace(Visibility=True),
    )
    piece = SimpleNamespace(
        Name="FrontPiece",
        Label="Front panel",
        GeometryAuthority="Sketcher",
        Sketch=front_sketch,
        ViewObject=SimpleNamespace(Visibility=True),
    )
    back_piece = SimpleNamespace(
        Name="BackPiece",
        Label="Back panel",
        GeometryAuthority="Sketcher",
        Sketch=back_sketch,
        ViewObject=SimpleNamespace(Visibility=True),
    )
    seam = SimpleNamespace(SeamId="seam-front", PatternA=piece, PatternB=back_piece)
    selection = _Selection()
    updates: list[tuple[str, str]] = []
    panel = SimpleNamespace(
        Gui=SimpleNamespace(Selection=selection),
        doc=document,
        cancel_pick_button=_VisibilityButton(),
        _active_picker=None,
    )

    def set_status(message: str, *, state: str = "info") -> None:
        updates.append((message, state))

    panel._set_status = set_status
    combo = _Combo(("", "front:edge:2"))
    picker = _TopologyRepairViewportPicker(panel, seam, "A", combo)
    panel._active_picker = picker
    panel.cancel_pick_button.setVisible(True)
    return panel, picker, combo, selection, updates


def test_viewport_picker_maps_only_the_matching_semantic_sketcher_edge() -> None:
    """Set the row combo to the semantic ID resolved from the picked EdgeN."""
    panel, picker, combo, selection, updates = _picker_fixture()

    with patch(
        "freecad_cloth.pattern.PatternTopologyRepair.current_edge_candidate_for_sketch_index",
        return_value={"id": "front:edge:2"},
    ) as resolve:
        picker.addSelection("ClothDocument", "FrontSketch", "Edge3")

    resolve.assert_called_once_with(picker.seam, "A", 2)
    assert combo.current_index == 1
    assert picker.armed is False
    assert panel._active_picker is None
    assert selection.observers == []
    assert panel.cancel_pick_button.visible is False
    assert picker.expected_piece.ViewObject.Visibility is True
    assert picker.expected_sketch.ViewObject.Visibility is False
    assert updates[-1][1] == "success"
    assert "Mapped seam seam-front side A" in updates[-1][0]


def test_viewport_picker_rejects_a_different_pattern_piece() -> None:
    """Keep the one-shot picker armed when the wrong source piece is clicked."""
    panel, picker, combo, selection, updates = _picker_fixture()

    with patch(
        "freecad_cloth.pattern.PatternTopologyRepair.current_edge_candidate_for_sketch_index"
    ) as resolve:
        picker.addSelection("ClothDocument", "BackSketch", "Edge3")

    resolve.assert_not_called()
    assert picker.armed is True
    assert panel._active_picker is picker
    assert combo.current_index == 0
    assert selection.observers == [picker]
    assert updates[-1][1] == "warning"
    assert "linked to seam side A" in updates[-1][0]


def test_viewport_picker_rejects_foreign_document_and_non_edge_hits() -> None:
    """Reject foreign documents and face hits without losing the active pick mode."""
    panel, picker, combo, selection, updates = _picker_fixture()

    with patch(
        "freecad_cloth.pattern.PatternTopologyRepair.current_edge_candidate_for_sketch_index"
    ) as resolve:
        picker.addSelection("OtherDocument", "FrontSketch", "Edge3")
        assert "active document" in updates[-1][0]
        picker.addSelection("ClothDocument", "FrontSketch", "Face1")

    resolve.assert_not_called()
    assert picker.armed is True
    assert combo.current_index == 0
    assert selection.observers == [picker]
    assert updates[-1][1] == "warning"
    assert "outline edge" in updates[-1][0]


def test_viewport_picker_cancels_and_unregisters_cleanly() -> None:
    """Remove the observer and restore original visibility on cancellation."""
    panel, picker, combo, selection, _updates = _picker_fixture()

    picker.dispose()

    assert picker.armed is False
    assert selection.observers == []
    assert panel._active_picker is None
    assert panel.cancel_pick_button.visible is False
    assert picker.expected_piece.ViewObject.Visibility is True
    assert picker.expected_sketch.ViewObject.Visibility is False
    assert combo.current_index == 0


def test_viewport_picker_rejects_a_semantic_edge_not_in_the_row_candidates() -> None:
    """Do not choose a semantically valid edge that is absent from this repair row."""
    panel, picker, combo, selection, updates = _picker_fixture()

    with patch(
        "freecad_cloth.pattern.PatternTopologyRepair.current_edge_candidate_for_sketch_index",
        return_value={"id": "front:edge:not-listed"},
    ):
        picker.addSelection("ClothDocument", "FrontSketch", "Edge3")

    assert picker.armed is True
    assert combo.current_index == 0
    assert selection.observers == [picker]
    assert updates[-1][1] == "warning"
    assert "not available in this seam-side repair row" in updates[-1][0]
