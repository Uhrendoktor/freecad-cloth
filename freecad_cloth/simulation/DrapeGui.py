# Copyright (C) 2026 FreeCAD Cloth contributors
"""FreeCAD task-panel frontend for the target-neutral drape object.

The persistent DrapeTarget document object remains authoritative. This panel
only stages target selection and collision settings until the user applies or
cancels the edit, following normal FreeCAD task-panel conventions.
"""

from __future__ import annotations

from types import ModuleType
from typing import TYPE_CHECKING, ClassVar, Protocol, cast

try:
    import FreeCAD as _App
except ImportError:
    _App = None

try:
    import FreeCADGui as _Gui
except ImportError:
    _Gui = None

try:
    from PySide import QtWidgets as _QtWidgets
except ImportError:
    try:
        from PySide2 import QtWidgets as _QtWidgets
    except ImportError:
        _QtWidgets = None

from freecad_cloth.common.UiDesign import (
    apply_panel_style as _apply_panel_style,
    mark_button as _mark_button,
    set_status as _set_status_label,
)
from freecad_cloth.simulation.DrapeTarget import assign_drape_target as _assign_drape_target

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


class _FreeCADDocument(Protocol):
    """Document operations and object inventory used by the task panel."""

    Objects: Sequence[object]
    recompute: Callable[[], None]


class _FreeCADApplication(Protocol):
    """Active-document member exported by the FreeCAD application module."""

    ActiveDocument: _FreeCADDocument | None


class _DrapeTargetFeature(Protocol):
    """Persisted target properties staged and updated by the editor."""

    TargetType: str
    SourceObject: object | None
    CollisionDeflection: float
    CollisionThickness: float
    Enabled: bool
    TargetStatus: str
    InvalidationReason: str


def _modules() -> tuple[_FreeCADApplication, ModuleType, ModuleType]:
    """Return the FreeCAD application, GUI, and Qt widgets modules.

    Returns:
        The application module, GUI module, and supported QtWidgets module.

    Raises:
        ImportError: If the FreeCAD host or supported Qt widgets are unavailable.
    """
    if _App is None or _Gui is None or _QtWidgets is None:
        msg = "FreeCAD GUI and PySide widgets are required to open the drape target panel"
        raise ImportError(msg)
    return cast("_FreeCADApplication", _App), _Gui, _QtWidgets


class DrapeTargetTaskPanel:
    """CLO-like grouped editor for a persistent DrapeTarget."""

    App: object
    Gui: object
    doc: object | None
    target: object | None

    PRESETS: ClassVar[tuple[tuple[str, float], ...]] = (
        ("Preview", 2.5),
        ("Normal", 1.0),
        ("Final", 0.35),
    )

    def __init__(self, target: object | None = None) -> None:
        """Build the staged collision-target editor.

        Args:
            target: Existing persistent target; the active document target is used by default.

        Raises:
            ImportError: If the FreeCAD GUI or supported Qt widgets are unavailable.
        """
        App, Gui, QtWidgets = _modules()
        self.App, self.Gui = App, Gui
        self.doc = App.ActiveDocument
        self.target = target or self._find_target()
        self.form = QtWidgets.QWidget()
        self.form.setObjectName("ClothDrapeTargetTaskPanel")
        root = QtWidgets.QVBoxLayout(self.form)

        title = QtWidgets.QLabel("Drape Target")
        title.setProperty("clothRole", "title")
        root.addWidget(title)

        source_group = QtWidgets.QGroupBox("Collision object")
        source_layout = QtWidgets.QFormLayout(source_group)
        self.target_type = QtWidgets.QComboBox()
        self.target_type.addItems(("Mannequin", "FreeCAD Geometry"))
        self.source = QtWidgets.QComboBox()
        self._source_objects: list[object] = []
        self._populate_sources()
        source_layout.addRow("Provider", self.target_type)
        source_layout.addRow("Source", self.source)
        root.addWidget(source_group)

        quality = QtWidgets.QGroupBox("Collision quality")
        quality_layout = QtWidgets.QFormLayout(quality)
        self.preset = QtWidgets.QComboBox()
        self.preset.addItems([name for name, _value in self.PRESETS])
        self.deflection = QtWidgets.QDoubleSpinBox()
        self.deflection.setRange(0.01, 100.0)
        self.deflection.setDecimals(2)
        self.deflection.setSuffix(" mm")
        self.thickness = QtWidgets.QDoubleSpinBox()
        self.thickness.setRange(0.0, 50.0)
        self.thickness.setDecimals(2)
        self.thickness.setSuffix(" mm")
        quality_layout.addRow("Preset", self.preset)
        quality_layout.addRow("Tessellation", self.deflection)
        quality_layout.addRow("Collision thickness", self.thickness)
        root.addWidget(quality)

        options = QtWidgets.QGroupBox("Target state")
        options_layout = QtWidgets.QFormLayout(options)
        self.enabled = QtWidgets.QCheckBox("Enable collision target")
        self.enabled.setToolTip("Disabled targets remain persisted but are not used for draping.")
        options_layout.addRow(self.enabled)
        root.addWidget(options)

        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        self.status.setObjectName("ClothDrapeTargetStatus")
        _set_status_label(self.status, "", state="info")
        root.addWidget(self.status)

        controls = QtWidgets.QHBoxLayout()
        self.apply_button = QtWidgets.QPushButton("Apply & Refresh")
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        _mark_button(self.apply_button, "primary")
        _mark_button(self.cancel_button, "secondary")
        controls.addWidget(self.apply_button)
        controls.addWidget(self.cancel_button)
        root.addLayout(controls)

        self._loading = False
        self._load()
        self.target_type.currentTextChanged.connect(self._provider_changed)
        self.preset.currentTextChanged.connect(self._preset_changed)
        self.deflection.valueChanged.connect(self._preview_status)
        self.thickness.valueChanged.connect(self._preview_status)
        self.enabled.toggled.connect(self._preview_status)
        self.apply_button.clicked.connect(self._apply)
        self.cancel_button.clicked.connect(self.reject)
        _apply_panel_style(self.form)

    def _set_status(self, text: str, state: str = "info") -> None:
        """Update task feedback using the shared semantic status treatment.

        Args:
            text: User-facing explanation of the current target state.
            state: Semantic presentation state such as info, warning, or error.
        """
        _set_status_label(self.status, text, state=state)

    def _find_target(self) -> object | None:
        """Find the existing persistent target in the active document.

        Returns:
            The DrapeTarget feature, or None when the document has no target.
        """
        if self.doc is None:
            return None
        document = cast("_FreeCADDocument", self.doc)
        get_object = cast("Callable[[str], object | None]", getattr(document, "getObject"))
        return get_object("DrapeTarget")

    def _populate_sources(self) -> None:
        """Refresh the source selector from valid document objects."""
        self._source_objects = []
        self.source.clear()
        if self.doc is None:
            return
        document = cast("_FreeCADDocument", self.doc)
        for obj in document.Objects:
            if obj is self.target:
                continue
            if (
                getattr(obj, "AvatarType", "") == "ClothAvatar"
                or hasattr(obj, "Shape")
                or hasattr(obj, "Mesh")
            ):
                self._source_objects.append(obj)
                self.source.addItem(str(getattr(obj, "Label", getattr(obj, "Name", ""))))

    def _load(self) -> None:
        """Populate controls from the current target without staging changes."""
        if self.target is None:
            self._set_status(
                "Create a Drape Target first, or select a mannequin/FreeCAD object.",
                state="warning",
            )
            self.apply_button.setEnabled(False)
            return
        self._loading = True
        target = cast("_DrapeTargetFeature", self.target)
        self.target_type.setCurrentText(str(getattr(target, "TargetType", "FreeCAD Geometry")))
        source_obj = getattr(target, "SourceObject", None)
        source_index = next(
            (i for i, obj in enumerate(self._source_objects) if obj is source_obj), -1
        )
        if source_index >= 0:
            self.source.setCurrentIndex(source_index)
        self.deflection.setValue(float(getattr(target, "CollisionDeflection", 1.0)))
        self.thickness.setValue(float(getattr(target, "CollisionThickness", 2.0)))
        self.enabled.setChecked(bool(getattr(target, "Enabled", True)))
        self._select_nearest_preset(self.deflection.value())
        self._loading = False
        self._refresh_status()

    def _provider_changed(self, _value: str) -> None:
        """Refresh source options after the provider type changes.

        Args:
            _value: Newly selected provider type emitted by the Qt signal.
        """
        if self._loading:
            return
        self._populate_sources()
        self._preview_status()

    def _select_nearest_preset(self, value: float) -> None:
        """Select the preset whose deflection is closest to a supplied value.

        Args:
            value: Collision-mesh deflection in millimetres.
        """
        nearest = min(range(len(self.PRESETS)), key=lambda i: abs(self.PRESETS[i][1] - value))
        self.preset.blockSignals(True)
        self.preset.setCurrentIndex(nearest)
        self.preset.blockSignals(False)

    def _preset_changed(self, name: str) -> None:
        """Apply a selected preset to the staged deflection control.

        Args:
            name: Human-readable preset name emitted by the Qt combo box.
        """
        if self._loading:
            return
        for preset_name, value in self.PRESETS:
            if preset_name == name:
                self.deflection.blockSignals(True)
                self.deflection.setValue(value)
                self.deflection.blockSignals(False)
                break
        self._preview_status()

    def _preview_status(self, *_args: object) -> None:
        """Explain that target changes remain staged until explicit acceptance.

        Args:
            _args: Optional values provided by Qt signal callbacks.
        """
        if self._loading:
            return
        self._set_status(
            "Staged target edits. Apply & Refresh to rebuild collision geometry; "
            "Cancel leaves the document unchanged.",
            state="warning",
        )

    def _refresh_status(self) -> None:
        """Render status and invalidation details from the persisted target."""
        if self.target is None:
            return
        target = cast("_DrapeTargetFeature", self.target)
        state = str(getattr(target, "TargetStatus", "unbuilt"))
        reason = str(getattr(target, "InvalidationReason", ""))
        message = f"Target status: {state}"
        if reason:
            message += " — " + reason
        self._set_status(
            message,
            state="error"
            if state.lower() in {"invalid", "unassigned", "stale", "blocked", "error"}
            else "info",
        )

    def _selected_source(self) -> object | None:
        """Return the currently selected collision source.

        Returns:
            The selected source object, or None when the selection is invalid.
        """
        index = self.source.currentIndex()
        if index < 0 or index >= len(self._source_objects):
            return None
        return self._source_objects[index]

    def _apply(self, *, assign_target: Callable[..., object] | None = None) -> bool:
        """Commit staged target settings and rebuild the collision representation.

        Args:
            assign_target: Optional assignment function supplied by a focused test.

        Returns:
            True after applying a valid selected source, or False if it is missing.
        """
        if self.target is None:
            return False
        source = self._selected_source()
        target_type = str(self.target_type.currentText())
        if source is None:
            self._set_status(
                "Select a collision object before applying the target.",
                state="warning",
            )
            return False
        if assign_target is None:
            assign_target = _assign_drape_target
        target = cast("_DrapeTargetFeature", self.target)
        target.CollisionDeflection = self.deflection.value()
        target.CollisionThickness = self.thickness.value()
        target.Enabled = self.enabled.isChecked()
        assign_target(target, source, target_type)
        if self.doc is not None:
            cast("_FreeCADDocument", self.doc).recompute()
        self._refresh_status()
        return True

    def accept(self) -> bool:
        """Apply staged edits and permit the task panel to close.

        Returns:
            True when the selected target was accepted; otherwise False.
        """
        return self._apply()

    def reject(self) -> bool:
        """Close the task panel without applying staged control values.

        Returns:
            True to allow FreeCAD to close the task panel.
        """
        gui = cast("ModuleType", self.Gui)
        active_document = cast("Callable[[], object | None]", getattr(gui, "activeDocument"))
        control = getattr(gui, "Control")
        active_dialog = cast("Callable[[], object | None]", getattr(control, "activeDialog"))
        close_dialog = cast("Callable[[], None]", getattr(control, "closeDialog"))
        if active_document() and active_dialog():
            close_dialog()
        return True

    def _standard_buttons(self) -> object:
        """Return the native OK and Cancel button flags for the task panel.

        Returns:
            The combined Qt button flags used to accept or cancel editing.
        """
        _App, _Gui, QtWidgets = _modules()
        return QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel

    def __getattr__(self, name: str) -> object:
        """Expose native FreeCAD callback spelling for the task-panel button API.

        Args:
            name: Attribute requested by FreeCAD or a caller.

        Returns:
            The bound native callback for supported host attribute names.

        Raises:
            AttributeError: If name does not identify a supported callback.
        """
        if name == "getStandardButtons":
            return self._standard_buttons
        raise AttributeError(name)


def show_drape_target_task(target: object | None = None) -> DrapeTargetTaskPanel:
    """Open the native FreeCAD task panel for a DrapeTarget.

    Args:
        target: Optional existing target; defaults to the active document target.

    Returns:
        The task-panel instance shown by the native GUI controller.

    Raises:
        ImportError: If FreeCAD GUI or supported Qt widgets are unavailable.
    """
    _App, Gui, _QtWidgets = _modules()
    panel = DrapeTargetTaskPanel(target)
    control = getattr(Gui, "Control")
    show_dialog = cast("Callable[[object], None]", getattr(control, "showDialog"))
    show_dialog(panel)
    return panel
