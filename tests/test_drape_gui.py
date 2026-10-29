# Copyright (C) 2026 FreeCAD Cloth contributors
"""Behavioral contracts for the native DrapeTarget task-panel frontend."""

from types import SimpleNamespace

import pytest

from freecad_cloth.simulation import DrapeGui
from tests.support.assertions import require

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
STAGED_PREVIEW_MESSAGE = (
    "Staged target edits. Apply & Refresh to rebuild collision geometry; "
    "Cancel leaves the document unchanged."
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


def _scalar(value: object = 0.0) -> SimpleNamespace:
    """Build a numeric or checkbox stand-in for a Qt scalar control.

    Args:
        value: Initial numeric value or boolean state.

    Returns:
        State object with the value and checkbox callbacks used by the panel.
    """
    scalar = SimpleNamespace(_value=value)

    def current_value() -> object:
        """Return the staged value."""
        return scalar._value

    def set_value(new_value: object) -> None:
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

    def set_text(value: object) -> None:
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
    panel.target = object()
    panel.source = _combo()
    panel.target_type = _combo(0)
    panel.target_type.items = [EXPECTED_SOURCE_TYPE]
    panel.preset = _combo(NORMAL_PRESET_INDEX)
    panel.preset.items = [name for name, _value in EXPECTED_PRESETS]
    panel.deflection = _scalar(DEFAULT_DEFLECTION_MM)
    panel.thickness = _scalar(DEFAULT_THICKNESS_MM)
    panel.enabled = _scalar(True)
    panel.status = _status()
    panel._source_objects = []
    panel._loading = False
    return panel


def test_presets_are_explicit_and_materially_distinct() -> None:
    """Keep the three authored collision-quality presets stable."""
    require(
        condition=DrapeGui.DrapeTargetTaskPanel.PRESETS == EXPECTED_PRESETS,
        message="Preview, Normal, and Final presets must retain their authored deflections.",
    )


def test_populate_sources_keeps_only_collision_capable_objects() -> None:
    """List mannequins, shapes, and meshes while excluding unrelated objects."""
    panel = _panel()
    avatar = SimpleNamespace(AvatarType="ClothAvatar", Label="Avatar")
    shape = SimpleNamespace(Shape=object(), Label="Shape")
    mesh = SimpleNamespace(Mesh=object(), Label="Mesh")
    ignored = SimpleNamespace(Label="Ignored")
    panel.doc = SimpleNamespace(Objects=(panel.target, avatar, shape, mesh, ignored))

    panel._populate_sources()

    require(
        condition=panel._source_objects == [avatar, shape, mesh],
        message="Only collision-capable objects should be offered as target sources.",
    )
    require(
        condition=panel.source.items == ["Avatar", "Shape", "Mesh"],
        message="Source labels must follow the document-object order.",
    )


def test_source_selection_is_bounds_checked() -> None:
    """Return a source only for an index within the source inventory."""
    panel = _panel()
    source = object()
    panel._source_objects = [source]

    panel.source.index = 0
    require(
        condition=panel._selected_source() is source,
        message="A valid source index must return the corresponding object.",
    )
    panel.source.index = -1
    require(
        condition=panel._selected_source() is None,
        message="A negative source index must return no selection.",
    )
    panel.source.index = 2
    require(
        condition=panel._selected_source() is None,
        message="An out-of-range source index must return no selection.",
    )


def test_nearest_preset_and_preset_change_update_deflection() -> None:
    """Select the closest preset and preview the requested final deflection."""
    panel = _panel()

    panel._select_nearest_preset(NEAR_NORMAL_DEFLECTION_MM)
    require(
        condition=panel.preset.index == NORMAL_PRESET_INDEX,
        message="A value near Normal must select the Normal preset.",
    )

    panel.preset = _combo()
    panel.preset.items = [name for name, _value in EXPECTED_PRESETS]
    panel._preset_changed("Final")
    require(
        condition=panel.deflection.value() == pytest.approx(EXPECTED_FINAL_DEFLECTION_MM),
        message="Selecting Final must stage its authored mesh deflection.",
    )
    require(
        condition="Staged target edits" in panel.status.text,
        message="Preset changes must be reported as staged edits.",
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

    require(
        condition=panel._apply_enabled is False,
        message="Apply must be disabled until a target has been created.",
    )
    require(
        condition="Create a Drape Target first" in panel.status.text,
        message="The missing-target state must explain the next user action.",
    )


def test_apply_persists_target_values_and_recomputes() -> None:
    """Commit the staged values, assign the selected source, and recompute once."""
    panel = _panel()
    source = object()
    target = SimpleNamespace(
        CollisionDeflection=DEFAULT_DEFLECTION_MM,
        CollisionThickness=DEFAULT_THICKNESS_MM,
        Enabled=True,
    )
    document_calls: list[str] = []
    assigned: list[tuple[object, object, str]] = []

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

    def assign_target(target_obj: object, source_obj: object, target_type: str) -> None:
        """Capture the assignment requested by the editor.

        Args:
            target_obj: Persistent target that is being updated.
            source_obj: Selected collision source.
            target_type: Source representation selected in the panel.
        """
        assigned.append((target_obj, source_obj, target_type))

    require(
        condition=panel._apply(assign_target=assign_target) is True,
        message="A valid selected source should allow target acceptance.",
    )
    require(
        condition=(
            target.CollisionDeflection,
            target.CollisionThickness,
            target.Enabled,
        )
        == (EXPECTED_FINAL_DEFLECTION_MM, EXPECTED_APPLIED_THICKNESS_MM, False),
        message="Applying the panel must persist its staged collision values.",
    )
    require(
        condition=assigned == [(target, source, EXPECTED_SOURCE_TYPE)],
        message="The target assignment must use the selected source and provider type.",
    )
    require(
        condition=tuple(document_calls) == EXPECTED_RECOMPUTE_CALLS,
        message="Accepting changes must recompute the owning document exactly once.",
    )


def test_apply_fails_closed_without_selected_source() -> None:
    """Reject target acceptance when the source selector has no valid selection."""
    panel = _panel()
    panel.doc = SimpleNamespace(recompute=lambda: None)
    panel.source = _combo(-1)
    panel.target_type = _combo()
    panel.target_type.items = [EXPECTED_SOURCE_TYPE]
    panel.target_type.index = 0

    require(
        condition=panel._apply() is False,
        message="A missing collision source must prevent accepting the target.",
    )
    require(
        condition=MISSING_SOURCE_MESSAGE in panel.status.text,
        message="The empty-selection state must explain how to recover.",
    )


def test_staged_preview_status_is_diagnostic_only() -> None:
    """Report staged settings without implying that the document has changed."""
    panel = _panel()
    panel._preview_status()
    require(
        condition=panel.status.text == STAGED_PREVIEW_MESSAGE,
        message="Preview must communicate that edits are staged until Apply & Refresh.",
    )


def test_refresh_status_reports_state_and_invalidation_reason() -> None:
    """Combine persisted target status and its invalidation reason in the label."""
    panel = _panel()
    panel.target = SimpleNamespace(TargetStatus="stale", InvalidationReason="source changed")

    panel._refresh_status()

    require(
        condition=panel.status.text == EXPECTED_STALE_STATUS,
        message="Status display must include both target state and invalidation reason.",
    )


def test_reject_closes_active_dialog() -> None:
    """Close an active FreeCAD dialog when the task panel is rejected."""
    panel = _panel()
    calls: list[str] = []
    setattr(
        panel,
        "Gui",
        SimpleNamespace(
            activeDocument=lambda: object(),
            Control=SimpleNamespace(
                activeDialog=lambda: object(),
                closeDialog=lambda: calls.append("close"),
            ),
        ),
    )

    require(
        condition=panel.reject() is True,
        message="Reject must permit the native task panel to close.",
    )
    require(
        condition=tuple(calls) == EXPECTED_CLOSE_CALLS,
        message="Reject must close the active native dialog exactly once.",
    )
