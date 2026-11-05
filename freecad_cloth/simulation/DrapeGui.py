# Copyright (C) 2026 FreeCAD Cloth contributors
"""FreeCAD task-panel frontend for the target-neutral drape object.

The persistent DrapeTarget document object remains authoritative. This panel
only stages target selection and collision settings until the user applies or
cancels the edit, following normal FreeCAD task-panel conventions.
"""

from __future__ import annotations

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

from freecad_cloth.common.UiDesign import apply_panel_style as _apply_panel_style
from freecad_cloth.common.UiDesign import mark_button as _mark_button
from freecad_cloth.common.UiDesign import set_status as _set_status_label
from freecad_cloth.simulation.DrapeTarget import assign_drape_target as _assign_drape_target

SIGNALS_BLOCKED = True
SIGNALS_UNBLOCKED = False

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from types import ModuleType


class _FreeCADDocument(Protocol):
    """Document operations and object inventory used by the task panel."""

    Objects: Sequence[object]
    getObject: Callable[[str], object | None]
    recompute: Callable[[], None]


class _FreeCADApplication(Protocol):
    """Active-document member exported by the FreeCAD application module."""

    ActiveDocument: _FreeCADDocument | None


class _FreeCADControl(Protocol):
    """Native task-panel callbacks used by the FreeCAD GUI controller."""

    activeDialog: Callable[[], object | None]
    closeDialog: Callable[[], None]
    showDialog: Callable[[object], None]


class _FreeCADGui(Protocol):
    """FreeCAD GUI operations used by the target task panel."""

    Control: _FreeCADControl
    activeDocument: Callable[[], object | None]


class _WidgetLayout(Protocol):
    """Layout operations required to assemble the target panel."""

    addWidget: Callable[[object], None]
    addLayout: Callable[[object], None]


class _DrapeTargetFeature(Protocol):
    """Persisted target properties staged and updated by the editor."""

    TargetType: str
    SourceObject: object | None
    CollisionDeflection: float
    CollisionThickness: float
    Enabled: bool
    TargetStatus: str
    InvalidationReason: str


def _modules() -> tuple[_FreeCADApplication, _FreeCADGui, ModuleType]:
    """Return the FreeCAD application, GUI, and Qt widgets modules.

    Returns:
        The application module, GUI module, and supported QtWidgets module.

    Raises:
        ImportError: If the FreeCAD host or supported Qt widgets are unavailable.
    """
    if _App is None or _Gui is None or _QtWidgets is None:
        msg = "FreeCAD GUI and PySide widgets are required to open the drape target panel"
        raise ImportError(msg)
    return (
        cast("_FreeCADApplication", _App),
        cast("_FreeCADGui", _Gui),
        cast("ModuleType", _QtWidgets),
    )


class DrapeTargetTaskPanel:
    """CLO-like grouped editor for a persistent DrapeTarget."""

    App: _FreeCADApplication
    Gui: _FreeCADGui
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
            target: Existing persistent target; otherwise use the active document target.
        """
        app_module, gui_module, qt_widgets = _modules()
        self.App, self.Gui = app_module, gui_module
        self.doc = app_module.ActiveDocument
        self.target = target or self._find_target()
        self.form = qt_widgets.QWidget()
        self.form.setObjectName("ClothDrapeTargetTaskPanel")
        root = cast("_WidgetLayout", qt_widgets.QVBoxLayout(self.form))

        title = qt_widgets.QLabel("Drape Target")
        title.setProperty("clothRole", "title")
        root.addWidget(title)
        root.addWidget(self._build_source_group(qt_widgets))
        root.addWidget(self._build_quality_group(qt_widgets))
        root.addWidget(self._build_state_group(qt_widgets))
        self._build_status_and_controls(qt_widgets, root)
        self._loading = False
        self._load()
        self._connect_callbacks()
        _apply_panel_style(self.form)

    def _build_source_group(self, qt_widgets: ModuleType) -> object:
        """Create the source-provider selector group.

        Args:
            qt_widgets: Supported Qt widgets module loaded by the FreeCAD host.

        Returns:
            The source-provider group box attached to the panel root.
        """
        group = qt_widgets.QGroupBox("Collision object")
        layout = qt_widgets.QFormLayout(group)
        self.target_type = qt_widgets.QComboBox()
        self.target_type.addItems(("Mannequin", "FreeCAD Geometry"))
        self.source = qt_widgets.QComboBox()
        self._source_objects: list[object] = []
        self._populate_sources()
        layout.addRow("Provider", self.target_type)
        layout.addRow("Source", self.source)
        return group

    def _build_quality_group(self, qt_widgets: ModuleType) -> object:
        """Create the staged collision-quality controls.

        Args:
            qt_widgets: Supported Qt widgets module loaded by the FreeCAD host.

        Returns:
            The collision-quality group box.
        """
        group = qt_widgets.QGroupBox("Collision quality")
        layout = qt_widgets.QFormLayout(group)
        self.preset = qt_widgets.QComboBox()
        self.preset.addItems([name for name, _value in self.PRESETS])
        self.deflection = qt_widgets.QDoubleSpinBox()
        self.deflection.setRange(0.01, 100.0)
        self.deflection.setDecimals(2)
        self.deflection.setSuffix(" mm")
        self.thickness = qt_widgets.QDoubleSpinBox()
        self.thickness.setRange(0.0, 50.0)
        self.thickness.setDecimals(2)
        self.thickness.setSuffix(" mm")
        layout.addRow("Preset", self.preset)
        layout.addRow("Tessellation", self.deflection)
        layout.addRow("Collision thickness", self.thickness)
        return group

    def _build_state_group(self, qt_widgets: ModuleType) -> object:
        """Create the target enabled-state checkbox.

        Args:
            qt_widgets: Supported Qt widgets module loaded by the FreeCAD host.

        Returns:
            The target-state group box.
        """
        group = qt_widgets.QGroupBox("Target state")
        layout = qt_widgets.QFormLayout(group)
        self.enabled = qt_widgets.QCheckBox("Enable collision target")
        self.enabled.setToolTip("Disabled targets remain persisted but are not used for draping.")
        layout.addRow(self.enabled)
        return group

    def _build_status_and_controls(
        self,
        qt_widgets: ModuleType,
        root: _WidgetLayout,
    ) -> None:
        """Create semantic status feedback and the Apply/Cancel buttons.

        Args:
            qt_widgets: Supported Qt widgets module loaded by the FreeCAD host.
            root: Main panel layout receiving the status and action controls.
        """
        self.status = qt_widgets.QLabel()
        self.status.setWordWrap(True)
        self.status.setObjectName("ClothDrapeTargetStatus")
        _set_status_label(self.status, "", state="info")
        root.addWidget(self.status)

        controls = qt_widgets.QHBoxLayout()
        self.apply_button = qt_widgets.QPushButton("Apply & Refresh")
        self.cancel_button = qt_widgets.QPushButton("Cancel")
        _mark_button(self.apply_button, "primary")
        _mark_button(self.cancel_button, "secondary")
        controls.addWidget(self.apply_button)
        controls.addWidget(self.cancel_button)
        root.addLayout(controls)

    def _connect_callbacks(self) -> None:
        """Connect UI change and action signals to the task-panel handlers."""
        self.target_type.currentTextChanged.connect(self._provider_changed)
        self.preset.currentTextChanged.connect(self._preset_changed)
        self.deflection.valueChanged.connect(self._preview_status)
        self.thickness.valueChanged.connect(self._preview_status)
        self.enabled.toggled.connect(self._preview_status)
        self.apply_button.clicked.connect(self._apply)
        self.cancel_button.clicked.connect(self.reject)

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
        return document.getObject("DrapeTarget")

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
        self.preset.blockSignals(SIGNALS_BLOCKED)
        self.preset.setCurrentIndex(nearest)
        self.preset.blockSignals(SIGNALS_UNBLOCKED)

    def _preset_changed(self, name: str) -> None:
        """Apply a selected preset to the staged deflection control.

        Args:
            name: Human-readable preset name emitted by the Qt combo box.
        """
        if self._loading:
            return
        for preset_name, value in self.PRESETS:
            if preset_name == name:
                self.deflection.blockSignals(SIGNALS_BLOCKED)
                self.deflection.setValue(value)
                self.deflection.blockSignals(SIGNALS_UNBLOCKED)
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
        gui = cast("_FreeCADGui", self.Gui)
        if gui.activeDocument() and gui.Control.activeDialog():
            gui.Control.closeDialog()
        return True

    @staticmethod
    def _standard_buttons() -> object:
        """Return the native OK and Cancel button flags for the task panel.

        Returns:
            The combined Qt button flags used to accept or cancel editing.
        """
        _app_module, _gui_module, qt_widgets = _modules()
        return qt_widgets.QDialogButtonBox.Ok | qt_widgets.QDialogButtonBox.Cancel

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

    """
    _app_module, gui_module, _qt_widgets = _modules()
    panel = DrapeTargetTaskPanel(target)
    gui_module.Control.showDialog(panel)
    return panel
