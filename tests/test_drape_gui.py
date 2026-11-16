# Copyright (C) 2026 FreeCAD Cloth contributors
"""Behavioral contracts for the native DrapeTarget task-panel frontend."""

from types import SimpleNamespace

import pytest

from freecad_cloth.simulation import DrapeGui

EXPECTED_PRESETS: tuple[tuple[str, float], ...] = (
    ("Preview", 2.5),
    ("Normal", 1.0),
    ("Final", 0.35),
)
DEFAULT_DEFLECTION_MM = 1.0
DEFAULT_THICKNESS_MM = 2.0
NEAR_NORMAL_DEFLECTION_MM = 1.2
EXPECTED_FINAL_DEFLECTION_MM = 0.35
EXPECTED_APPLIED_THICKNESS_MM = 3.0
NORMAL_PRESET_INDEX = 1
FINAL_PRESET_INDEX = 2
EXPECTED_SOURCE_TYPE = "FreeCAD Geometry"

type _ScalarValue = bool | float | int
STAGED_PREVIEW_MESSAGE = (
    "Staged target edits. Apply & Refresh commits the collision settings now; "
    "Cancel closes without applying further edits."
)
EXPECTED_STALE_STATUS = "Target status: stale — source changed"
MISSING_SOURCE_MESSAGE = "Select a collision object"
EXPECTED_RECOMPUTE_CALLS = ("recompute",)
EXPECTED_CLOSE_CALLS = ("close",)


def _combo(index: int = -1) -> SimpleNamespace:
    """Build a combo-box stand-in with dynamically named Qt callables.

    Args:
        index: Initial selected index; -1 represents no selection.

    Returns:
        Combo-box state and the callback attributes used by the task panel.
    """
    combo = SimpleNamespace(index=index, items=[], blocked=[])

    def clear() -> None:
        """Clear available entries and reset the selected index."""
        combo.items.clear()
        combo.index = -1

    def add_item(value: str) -> None:
        """Append one displayed item.

        Args:
            value: Human-readable entry added to the combo box.
        """
        combo.items.append(value)

    def current_index() -> int:
        """Return the currently selected entry index."""
        return combo.index

    def set_current_index(value: int) -> None:
        """Select an entry by index.

        Args:
            value: Entry index to select.
        """
        combo.index = value

    def set_current_text(value: str) -> None:
        """Select the entry matching a displayed string.

        Args:
            value: Existing entry text to select.
        """
        combo.index = combo.items.index(value)

    def current_text() -> str:
        """Return the selected entry text."""
        return combo.items[combo.index]

    def block_signals(value: bool) -> None:
        """Record the requested signal-blocking state.

        Args:
            value: Whether combo-box signals should be blocked.
        """
        combo.blocked.append(bool(value))

    combo.clear = clear
    combo.addItem = add_item
    combo.currentIndex = current_index
    combo.setCurrentIndex = set_current_index
    combo.setCurrentText = set_current_text
    combo.currentText = current_text
    combo.blockSignals = block_signals
    return combo


def _scalar(value: _ScalarValue = 0.0) -> SimpleNamespace:
    """Build a numeric or checkbox stand-in for a Qt scalar control.

    Args:
        value: Initial numeric value or boolean state.

    Returns:
        State object with the value and checkbox callbacks used by the panel.
    """
    scalar = SimpleNamespace(_value=value)

    def current_value() -> _ScalarValue:
        """Return the staged value."""
        return scalar._value

    def set_value(new_value: _ScalarValue) -> None:
        """Update the staged value.

        Args:
            new_value: Numeric value or boolean state to retain.
        """
        scalar._value = new_value

    def is_checked() -> bool:
        """Return the staged checkbox state."""
        return bool(scalar._value)

    def set_checked(new_value: bool) -> None:
        """Update the staged checkbox state.

        Args:
            new_value: New checkbox state.
        """
        scalar._value = bool(new_value)

    def block_signals(_value: bool) -> None:
        """Accept signal blocking without triggering callbacks.

        Args:
            _value: Whether signals should be blocked.
        """

    scalar.value = current_value
    scalar.setValue = set_value
    scalar.isChecked = is_checked
    scalar.setChecked = set_checked
    scalar.blockSignals = block_signals
    return scalar


def _status() -> SimpleNamespace:
    """Build a status-label stand-in used by semantic status rendering.

    Returns:
        Label state and Qt-style callbacks for text, properties, and styling.
    """
    status = SimpleNamespace(text="", properties={})

    def set_text(value: str) -> None:
        """Store the visible status text.

        Args:
            value: Text supplied by the task-panel status helper.
        """
        status.text = str(value)

    def set_property(name: str, value: str) -> None:
        """Store a dynamic style property.

        Args:
            name: Qt property name.
            value: String property value.
        """
        status.properties[name] = value

    def set_word_wrap(_value: bool) -> None:
        """Accept the label word-wrapping request.

        Args:
            _value: Whether label text should wrap across lines.
        """

    def style() -> None:
        """Return no GUI style object for the headless fixture."""

    def update() -> None:
        """Accept a label refresh request."""

    status.setText = set_text
    status.setProperty = set_property
    status.setWordWrap = set_word_wrap
    status.style = style
    status.update = update
    return status


def _panel() -> DrapeGui.DrapeTargetTaskPanel:
    """Build an uninitialized task panel with isolated headless widgets.

    Returns:
        Task-panel instance whose UI elements are simple in-memory stand-ins.
    """
    panel = DrapeGui.DrapeTargetTaskPanel.__new__(DrapeGui.DrapeTargetTaskPanel)
    panel.target = SimpleNamespace()
    panel.source = _combo()
    panel.target_type = _combo(1)
    panel.target_type.items = ["Mannequin", EXPECTED_SOURCE_TYPE]
    panel.preset = _combo(NORMAL_PRESET_INDEX)
    panel.preset.items = [name for name, _value in EXPECTED_PRESETS]
    panel.deflection = _scalar(DEFAULT_DEFLECTION_MM)
    panel.thickness = _scalar(DEFAULT_THICKNESS_MM)
    panel.enabled = _scalar(True)
    panel.status = _status()
    panel._source_objects = []
    panel._source_picker = None
    panel._loading = False
    return panel



class _Button:
    """Capture viewport action availability and transient pick visibility."""

    def __init__(self) -> None:
        self.enabled = True
        self.visible = True

    def setEnabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)

    def setVisible(self, visible: bool) -> None:
        self.visible = bool(visible)


class _Selection:
    """Capture the FreeCAD selection-observer and highlight lifecycle."""

    def __init__(self) -> None:
        self.observers: list[object] = []
        self.calls: list[tuple[object, ...]] = []

    def addObserver(self, observer: object) -> None:
        self.observers.append(observer)

    def removeObserver(self, observer: object) -> None:
        self.observers.remove(observer)

    def clearSelection(self) -> None:
        self.calls.append(("clear",))

    def addSelection(self, source: object) -> None:
        self.calls.append(("select", source))


def _viewport_panel(source: SimpleNamespace) -> tuple[DrapeGui.DrapeTargetTaskPanel, _Selection]:
    """Build a headless panel with the viewport source actions wired to doubles."""
    panel = _panel()
    panel.doc = SimpleNamespace(
        Name="ClothDocument",
        Objects=(source,),
        getObject=lambda name: source if name == source.Name else None,
    )
    panel.Gui = SimpleNamespace(Selection=_Selection())
    panel._source_objects = [source]
    panel.source = _combo()
    panel.source.addItem(str(source.Label))
    panel.target_type = _combo(1)
    panel.target_type.items = ["Mannequin", EXPECTED_SOURCE_TYPE]
    panel.apply_button = _Button()
    panel.pick_source_button = _Button()
    panel.cancel_pick_button = _Button()
    panel.show_source_button = _Button()
    return panel, panel.Gui.Selection


def test_viewport_pick_is_disabled_without_eligible_document_sources() -> None:
    """Avoid arming a viewport picker when no valid collision source can be selected."""
    source = SimpleNamespace(Name="CollisionBody", Label="Collision Body", Shape=object())
    panel, _selection = _viewport_panel(source)
    panel._source_objects = []

    panel._update_source_actions()

    assert panel.pick_source_button.enabled is False
    assert panel.show_source_button.enabled is False
    assert panel.apply_button.enabled is False


def test_viewport_pick_stages_source_and_releases_selection_observer() -> None:
    """Pick a document object in 3D and return to the normal panel actions."""
    source = SimpleNamespace(Name="CollisionBody", Label="Collision Body", Shape=object())
    panel, selection = _viewport_panel(source)

    panel._begin_source_pick()
    picker = panel._source_picker

    assert picker is not None
    assert selection.observers == [picker]
    assert panel.pick_source_button.enabled is False
    assert panel.cancel_pick_button.visible is True

    picker.addSelection("ClothDocument", "CollisionBody", "Face3")

    assert panel.source.currentIndex() == 0
    assert panel.apply_button.enabled is True
    assert panel.show_source_button.enabled is True
    assert panel._source_picker is None
    assert selection.observers == []
    assert panel.cancel_pick_button.visible is False
    assert panel.pick_source_button.enabled is True
    assert "Picked Collision Body" in panel.status.text
    assert panel.status.properties["clothState"] == "info"


def test_viewport_pick_rejects_objects_from_another_document() -> None:
    """Keep the picker armed when a selection belongs to a different document."""
    source = SimpleNamespace(Name="CollisionBody", Label="Collision Body", Shape=object())
    panel, selection = _viewport_panel(source)

    panel._begin_source_pick()
    picker = panel._source_picker
    assert picker is not None

    picker.addSelection("OtherDocument", "CollisionBody", "Face1")

    assert picker.armed is True
    assert panel._source_picker is picker
    assert panel.status.properties["clothState"] == "warning"
    assert "active document" in panel.status.text
    assert selection.observers == [picker]


def test_viewport_pick_rejects_unlisted_objects_and_remains_armed() -> None:
    """Do not accept a document object unless it is in the panel's valid source list."""
    source = SimpleNamespace(Name="CollisionBody", Label="Collision Body", Shape=object())
    unrelated = SimpleNamespace(Name="PatternSketch", Label="Pattern Sketch", Shape=object())
    panel, selection = _viewport_panel(source)
    panel.doc = SimpleNamespace(
        Name="ClothDocument",
        getObject=lambda name: unrelated if name == "PatternSketch" else source,
    )

    panel._begin_source_pick()
    picker = panel._source_picker
    assert picker is not None

    picker.addSelection("ClothDocument", "PatternSketch", "Face1")

    assert picker.armed is True
    assert panel._source_picker is picker
    assert "not an available" in panel.status.text
    assert panel.status.properties["clothState"] == "warning"
    assert selection.observers == [picker]


def test_viewport_pick_chooses_mannequin_provider_for_avatar_sources() -> None:
    """Synchronize viewport selection with the matching mannequin provider."""
    source = SimpleNamespace(
        Name="ClothAvatar",
        Label="Cloth Mannequin",
        AvatarType="ClothAvatar",
        Shape=object(),
    )
    panel, selection = _viewport_panel(source)
    panel._begin_source_pick()
    picker = panel._source_picker
    assert picker is not None

    picker.addSelection("ClothDocument", "ClothAvatar", "")

    assert panel.target_type.currentText() == "Mannequin"
    assert panel.source.currentIndex() == 0
    assert panel._source_picker is None
    assert selection.observers == []


def test_select_source_in_view_uses_native_selection_without_camera_changes() -> None:
    """Highlight the current collision source without altering the view camera."""
    source = SimpleNamespace(Name="CollisionBody", Label="Collision Body", Shape=object())
    panel, selection = _viewport_panel(source)
    panel.source.setCurrentIndex(0)

    assert panel._select_source_in_view() is True
    assert selection.calls == [("clear",), ("select", source)]
    assert panel.status.properties["clothState"] == "info"
    assert "without moving the camera" in panel.status.text


def test_accept_cancels_an_unfinished_viewport_pick_before_validation() -> None:
    """Do not leave a selection observer installed after the native OK action."""
    source = SimpleNamespace(Name="CollisionBody", Label="Collision Body", Shape=object())
    panel, selection = _viewport_panel(source)
    panel._begin_source_pick()
    picker = panel._source_picker
    assert picker is not None

    assert panel.accept() is False
    assert picker.armed is False
    assert selection.observers == []
    assert panel._source_picker is None


def test_cancel_and_reject_remove_viewport_selection_observer() -> None:
    """Unregister the temporary selection observer on either exit path."""
    source = SimpleNamespace(Name="CollisionBody", Label="Collision Body", Shape=object())
    panel, selection = _viewport_panel(source)
    panel._begin_source_pick()
    picker = panel._source_picker
    assert picker is not None

    panel._cancel_source_pick()
    assert picker.armed is False
    assert selection.observers == []
    assert panel._source_picker is None
    assert panel.status.properties["clothState"] == "info"

    panel._begin_source_pick()
    picker = panel._source_picker
    assert picker is not None
    panel.Gui.activeDocument = lambda: None
    panel.Gui.Control = SimpleNamespace(activeDialog=lambda: None, closeDialog=lambda: None)
    panel.reject()
    assert picker.armed is False
    assert selection.observers == []
    assert panel._source_picker is None


def test_presets_are_explicit_and_materially_distinct() -> None:
    """Keep the three authored collision-quality presets stable."""
    assert DrapeGui.DrapeTargetTaskPanel.PRESETS == EXPECTED_PRESETS, (
        "Preview, Normal, and Final presets must retain their authored deflections."
    )


def test_populate_sources_keeps_only_collision_capable_objects() -> None:
    """List mannequins, shapes, and meshes while excluding unrelated objects."""
    panel = _panel()
    avatar = SimpleNamespace(AvatarType="ClothAvatar", Label="Avatar")
    shape = SimpleNamespace(Shape=SimpleNamespace(), Label="Shape")
    mesh = SimpleNamespace(Mesh=SimpleNamespace(), Label="Mesh")
    ignored = SimpleNamespace(Label="Ignored")
    panel.doc = SimpleNamespace(Objects=(panel.target, avatar, shape, mesh, ignored))

    panel._populate_sources()

    assert panel._source_objects == [avatar, shape, mesh], (
        "Only collision-capable objects should be offered as target sources."
    )
    assert panel.source.items == ["Avatar", "Shape", "Mesh"], (
        "Source labels must follow the document-object order."
    )


def test_source_selection_is_bounds_checked() -> None:
    """Return a source only for an index within the source inventory."""
    panel = _panel()
    source = SimpleNamespace()
    panel._source_objects = [source]

    panel.source.index = 0
    assert panel._selected_source() is source, (
        "A valid source index must return the corresponding object."
    )
    panel.source.index = -1
    assert panel._selected_source() is None, "A negative source index must return no selection."
    panel.source.index = 2
    assert panel._selected_source() is None, (
        "An out-of-range source index must return no selection."
    )


def test_nearest_preset_and_preset_change_update_deflection() -> None:
    """Select the closest preset and preview the requested final deflection."""
    panel = _panel()

    panel._select_nearest_preset(NEAR_NORMAL_DEFLECTION_MM)
    assert panel.preset.index == NORMAL_PRESET_INDEX, (
        "A value near Normal must select the Normal preset."
    )

    panel.preset = _combo()
    panel.preset.items = [name for name, _value in EXPECTED_PRESETS]
    panel._preset_changed("Final")
    assert panel.deflection.value() == pytest.approx(EXPECTED_FINAL_DEFLECTION_MM), (
        "Selecting Final must stage its authored mesh deflection."
    )
    assert "Staged target edits" in panel.status.text, (
        "Preset changes must be reported as staged edits."
    )


def test_missing_target_disables_apply_and_reports_action() -> None:
    """Disable applying when no persistent target is available."""
    panel = _panel()
    panel.target = None
    panel.apply_button = SimpleNamespace(
        setEnabled=lambda value: setattr(panel, "_apply_enabled", value)
    )
    panel.doc = SimpleNamespace()

    panel._load()

    assert panel._apply_enabled is False, "Apply must be disabled until a target has been created."
    assert "Create a Drape Target first" in panel.status.text, (
        "The missing-target state must explain the next user action."
    )


def test_apply_persists_target_values_and_recomputes() -> None:
    """Commit the staged values, assign the selected source, and recompute once."""
    panel = _panel()
    source = SimpleNamespace()
    target = SimpleNamespace(
        CollisionDeflection=DEFAULT_DEFLECTION_MM,
        CollisionThickness=DEFAULT_THICKNESS_MM,
        Enabled=True,
    )
    document_calls: list[str] = []
    assigned: list[tuple[SimpleNamespace, SimpleNamespace, str]] = []

    panel.target = target
    panel.source = _combo(0)
    panel.target_type = _combo()
    panel.target_type.items = [EXPECTED_SOURCE_TYPE]
    panel.target_type.index = 0
    panel.deflection.setValue(EXPECTED_FINAL_DEFLECTION_MM)
    panel.thickness.setValue(EXPECTED_APPLIED_THICKNESS_MM)
    panel.enabled.setChecked(False)
    panel._source_objects = [source]
    panel.doc = SimpleNamespace(recompute=lambda: document_calls.append("recompute"))

    def assign_target(
        target_obj: SimpleNamespace, source_obj: SimpleNamespace, target_type: str
    ) -> None:
        """Capture the assignment requested by the editor.

        Args:
            target_obj: Persistent target that is being updated.
            source_obj: Selected collision source.
            target_type: Source representation selected in the panel.
        """
        assigned.append((target_obj, source_obj, target_type))

    assert panel._apply(assign_target=assign_target) is True, (
        "A valid selected source should allow target acceptance."
    )
    assert (
        target.CollisionDeflection,
        target.CollisionThickness,
        target.Enabled,
    ) == (EXPECTED_FINAL_DEFLECTION_MM, EXPECTED_APPLIED_THICKNESS_MM, False), (
        "Applying the panel must persist its staged collision values."
    )
    assert assigned == [(target, source, EXPECTED_SOURCE_TYPE)], (
        "The target assignment must use the selected source and provider type."
    )
    assert tuple(document_calls) == EXPECTED_RECOMPUTE_CALLS, (
        "Accepting changes must recompute the owning document exactly once."
    )


def test_apply_fails_closed_without_selected_source() -> None:
    """Reject target acceptance when the source selector has no valid selection."""
    panel = _panel()
    panel.doc = SimpleNamespace(recompute=lambda: None)
    panel.source = _combo(-1)
    panel.target_type = _combo()
    panel.target_type.items = [EXPECTED_SOURCE_TYPE]
    panel.target_type.index = 0

    assert panel._apply() is False, "A missing collision source must prevent accepting the target."
    assert MISSING_SOURCE_MESSAGE in panel.status.text, (
        "The empty-selection state must explain how to recover."
    )


def test_staged_preview_status_is_diagnostic_only() -> None:
    """Report staged settings without implying that the document has changed."""
    panel = _panel()
    panel._preview_status()
    assert panel.status.text == STAGED_PREVIEW_MESSAGE, (
        "Preview must communicate that edits are staged until Apply & Refresh."
    )


def test_refresh_status_reports_state_and_invalidation_reason() -> None:
    """Combine persisted target status and its invalidation reason in the label."""
    panel = _panel()
    panel.target = SimpleNamespace(TargetStatus="stale", InvalidationReason="source changed")

    panel._refresh_status()

    assert panel.status.text == EXPECTED_STALE_STATUS, (
        "Status display must include both target state and invalidation reason."
    )


def test_refresh_status_marks_ready_target_as_success() -> None:
    """Show a ready collision target as successful rather than neutral information."""
    panel = _panel()
    panel.target = SimpleNamespace(TargetStatus="ready", InvalidationReason="")
    panel._refresh_status()

    assert panel.status.text == "Target status: ready"
    assert panel.status.properties["clothState"] == "success"


def test_reject_closes_active_dialog() -> None:
    """Close an active FreeCAD dialog when the task panel is rejected."""
    panel = _panel()
    calls: list[str] = []
    panel.Gui = SimpleNamespace(
        activeDocument=lambda: SimpleNamespace(),
        Control=SimpleNamespace(
            activeDialog=lambda: SimpleNamespace(), closeDialog=lambda: calls.append("close")
        ),
    )

    assert panel.reject() is True, "Reject must permit the native task panel to close."
    assert tuple(calls) == EXPECTED_CLOSE_CALLS, (
        "Reject must close the active native dialog exactly once."
    )
