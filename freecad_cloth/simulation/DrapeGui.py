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

if TYPE_CHECKING:
    from PySide2 import QtWidgets as _QtWidgets
else:
    try:
        from PySide import QtWidgets as _QtWidgets
    except ImportError:
        try:
            from PySide2 import QtWidgets as _QtWidgets
        except ImportError:
            _QtWidgets = None

from freecad_cloth.common.garment_document import FreeCADDocumentObjectProtocol
from freecad_cloth.common.UiDesign import apply_panel_style as _apply_panel_style
from freecad_cloth.common.UiDesign import configure_form_layout as _configure_form_layout
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

    Objects: Sequence[FreeCADDocumentObjectProtocol]
    getObject: Callable[[str], FreeCADDocumentObjectProtocol | None]
    recompute: Callable[[], None]


class _FreeCADApplication(Protocol):
    """Active-document member exported by the FreeCAD application module."""

    ActiveDocument: _FreeCADDocument | None


class _TaskPanelDialog(Protocol):
    """Truth-testable task-panel dialog returned by FreeCAD's control API."""

    def __bool__(self) -> bool:
        """Return whether a task-panel dialog is currently active."""
        ...


class _FreeCADControl(Protocol):
    """Native task-panel callbacks used by the FreeCAD GUI controller."""

    activeDialog: Callable[[], _TaskPanelDialog | None]
    closeDialog: Callable[[], None]
    showDialog: Callable[[DrapeTargetTaskPanel], None]


class _GuiDocument(Protocol):
    """Truth-testable active GUI document handle returned by FreeCADGui."""

    def __bool__(self) -> bool:
        """Return whether a GUI document is currently active."""
        ...


class _FreeCADSelection(Protocol):
    """Selection operations used by the viewport source picker."""

    def addObserver(self, observer: object) -> None:
        """Register an observer for subsequent viewport selections."""
        ...

    def removeObserver(self, observer: object) -> None:
        """Unregister a previously registered selection observer."""
        ...

    def clearSelection(self) -> None:
        """Clear the current GUI selection."""
        ...

    def addSelection(self, source: object) -> None:
        """Select one existing document object in the 3D view."""
        ...


class _FreeCADGui(Protocol):
    """FreeCAD GUI operations used by the target task panel."""

    Control: _FreeCADControl
    Selection: _FreeCADSelection
    activeDocument: Callable[[], _GuiDocument | None]


class _PanelWidget(Protocol):
    """Qt widget operations shared by the task-panel's group and status controls."""

    def setProperty(self, name: str, value: str) -> None:
        """Set a semantic style property consumed by the panel stylesheet."""
        ...

    def setObjectName(self, name: str) -> None:
        """Assign a stable object name for host integration and tests."""
        ...

    def setToolTip(self, text: str) -> None:
        """Set the explanatory tooltip shown by the control."""
        ...

    def setWordWrap(self, enabled: bool) -> None:
        """Control whether the status label wraps long messages."""
        ...

    def setEnabled(self, enabled: bool) -> None:
        """Enable or disable user interaction with the widget."""
        ...

    def setVisible(self, visible: bool) -> None:
        """Show or hide an optional viewport-picking action."""
        ...


class _WidgetLayout(Protocol):
    """Layout operations required to assemble the target panel."""

    def addWidget(self, widget: _PanelWidget) -> None:
        """Add one widget to the current layout."""
        ...

    def addLayout(self, layout: _WidgetLayout) -> None:
        """Add a nested layout to the current layout."""
        ...


class _DrapeTargetFeature(FreeCADDocumentObjectProtocol, Protocol):
    """Persisted target properties staged and updated by the editor."""

    TargetType: str
    SourceObject: FreeCADDocumentObjectProtocol | None
    CollisionDeflection: float
    CollisionThickness: float
    Enabled: bool
    TargetStatus: str
    InvalidationReason: str
    addProperty: Callable[[str, str, str], FreeCADDocumentObjectProtocol]


type _AssignDrapeTarget = Callable[
    [_DrapeTargetFeature, FreeCADDocumentObjectProtocol, str],
    _DrapeTargetFeature,
]
type _QtSignalValue = str | float | bool


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


class _ViewportSourcePicker:
    """Select one existing collision source directly from the FreeCAD viewport."""

    def __init__(self, panel: DrapeTargetTaskPanel) -> None:
        """Register a one-shot selection observer owned by the current task panel.

        Args:
            panel: Drape Target panel receiving the selected source.
        """
        self.panel = panel
        self.armed = True
        self.Gui = panel.Gui
        self.Gui.Selection.addObserver(self)

    def addSelection(
        self,
        document_name: str,
        object_name: str,
        _subelement_name: str,
        *_position: object,
    ) -> None:
        """Accept a viewport object selection when it belongs to the active document.

        Args:
            document_name: Internal name of the document that owns the selected object.
            object_name: Internal name of the selected document object.
            _subelement_name: Selected face/edge name, ignored because the whole source is used.
            *_position: Optional world-space hit coordinates provided by FreeCAD.
        """
        if not self.armed:
            return
        expected_document = str(getattr(self.panel.doc, "Name", ""))
        if document_name and expected_document and str(document_name) != expected_document:
            self.panel._set_status(
                "Pick a collision source from the active document.",
                state="warning",
            )
            return
        document = self.panel.doc
        try:
            source = document.getObject(str(object_name)) if document is not None else None
        except (AttributeError, RuntimeError, TypeError, ValueError):
            source = None
        if source is None:
            source = next(
                (
                    candidate
                    for candidate in self.panel._source_objects
                    if str(getattr(candidate, "Name", "")) == str(object_name)
                ),
                None,
            )
        if source is None or not self.panel._select_source_object(source):
            self.panel._set_status(
                "That object is not an available mannequin, shape, or mesh collision source.",
                state="warning",
            )
            return
        label = str(getattr(source, "Label", getattr(source, "Name", "collision source")))
        self.dispose()
        self.panel._set_status(
            f"Picked {label} from the 3D view. Apply & Refresh commits the collision target.",
            state="info",
        )

    def dispose(self) -> None:
        """Unregister the observer and restore the task-panel pick controls."""
        if not self.armed:
            return
        self.armed = False
        try:
            self.Gui.Selection.removeObserver(self)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            pass
        if self.panel._source_picker is self:
            self.panel._source_picker = None
        self.panel.cancel_pick_button.setVisible(False)
        self.panel.pick_source_button.setEnabled(
            self.panel.target is not None
            and self.panel.doc is not None
            and bool(self.panel._source_objects)
        )


class DrapeTargetTaskPanel:
    """CLO-like grouped editor for a persistent DrapeTarget."""

    App: _FreeCADApplication
    Gui: _FreeCADGui
    doc: _FreeCADDocument | None
    target: _DrapeTargetFeature | None

    PRESETS: ClassVar[tuple[tuple[str, float], ...]] = (
        ("Preview", 2.5),
        ("Normal", 1.0),
        ("Final", 0.35),
    )

    def __init__(self, target: _DrapeTargetFeature | None = None) -> None:
        """Build the staged collision-target editor.

        Args:
            target: Existing persistent target; otherwise use the active document target.
        """
        app_module, gui_module, qt_widgets = _modules()
        self.App, self.Gui = app_module, gui_module
        self.doc = app_module.ActiveDocument
        self.target = target or self._find_target()
        self._source_picker: _ViewportSourcePicker | None = None
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
        self._update_source_actions()
        _apply_panel_style(self.form)

    def _build_source_group(self, qt_widgets: ModuleType) -> _PanelWidget:
        """Create the source-provider selector group.

        Args:
            qt_widgets: Supported Qt widgets module loaded by the FreeCAD host.

        Returns:
            The source-provider group box attached to the panel root.
        """
        group = qt_widgets.QGroupBox("Collision object")
        layout = qt_widgets.QFormLayout(group)
        _configure_form_layout(layout, qt_widgets)
        self.target_type = qt_widgets.QComboBox()
        self.target_type.addItems(("Mannequin", "FreeCAD Geometry"))
        self.source = qt_widgets.QComboBox()
        self._source_objects: list[FreeCADDocumentObjectProtocol] = []
        self._populate_sources()
        layout.addRow("Provider", self.target_type)
        layout.addRow("Source", self.source)

        viewport_actions = qt_widgets.QWidget()
        viewport_layout = qt_widgets.QGridLayout(viewport_actions)
        viewport_layout.setContentsMargins(0, 0, 0, 0)
        viewport_layout.setHorizontalSpacing(4)
        viewport_layout.setVerticalSpacing(4)
        self.pick_source_button = qt_widgets.QPushButton("Pick in 3D")
        self.pick_source_button.setToolTip(
            "Choose a mannequin, shape, or mesh by clicking it in the FreeCAD viewport."
        )
        self.cancel_pick_button = qt_widgets.QPushButton("Cancel pick")
        self.cancel_pick_button.setToolTip(
            "Leave viewport-picking mode without changing the target."
        )
        self.cancel_pick_button.setVisible(False)
        self.show_source_button = qt_widgets.QPushButton("Highlight in 3D")
        self.show_source_button.setToolTip(
            "Highlight the selected collision source in the FreeCAD viewport."
        )
        _mark_button(self.pick_source_button, "secondary")
        _mark_button(self.cancel_pick_button, "secondary")
        _mark_button(self.show_source_button, "secondary")
        viewport_layout.addWidget(self.pick_source_button, 0, 0)
        viewport_layout.addWidget(self.show_source_button, 0, 1)
        viewport_layout.addWidget(self.cancel_pick_button, 1, 0)
        viewport_layout.setColumnStretch(0, 1)
        viewport_layout.setColumnStretch(1, 1)
        layout.addRow("Viewport", viewport_actions)
        return group

    def _build_quality_group(self, qt_widgets: ModuleType) -> _PanelWidget:
        """Create the staged collision-quality controls.

        Args:
            qt_widgets: Supported Qt widgets module loaded by the FreeCAD host.

        Returns:
            The collision-quality group box.
        """
        group = qt_widgets.QGroupBox("Collision quality")
        layout = qt_widgets.QFormLayout(group)
        _configure_form_layout(layout, qt_widgets)
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

    def _build_state_group(self, qt_widgets: ModuleType) -> _PanelWidget:
        """Create the target enabled-state checkbox.

        Args:
            qt_widgets: Supported Qt widgets module loaded by the FreeCAD host.

        Returns:
            The target-state group box.
        """
        group = qt_widgets.QGroupBox("Target state")
        layout = qt_widgets.QFormLayout(group)
        _configure_form_layout(layout, qt_widgets)
        self.enabled = qt_widgets.QCheckBox("Enable collision target")
        self.enabled.setToolTip("Disabled targets remain persisted but are not used for draping.")
        layout.addRow(self.enabled)
        return group

    def _build_status_and_controls(
        self,
        qt_widgets: ModuleType,
        root: _WidgetLayout,
    ) -> None:
        """Create semantic status feedback and the primary apply action.

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
        self.apply_button.setToolTip(
            "Rebuild the collision representation with the currently staged settings."
        )
        _mark_button(self.apply_button, "primary")
        controls.addWidget(self.apply_button)
        controls.addStretch(1)
        root.addLayout(controls)

    def _connect_callbacks(self) -> None:
        """Connect UI change and action signals to the task-panel handlers."""
        self.target_type.currentTextChanged.connect(self._provider_changed)
        self.preset.currentTextChanged.connect(self._preset_changed)
        self.deflection.valueChanged.connect(self._preview_status)
        self.thickness.valueChanged.connect(self._preview_status)
        self.enabled.toggled.connect(self._preview_status)
        self.source.currentIndexChanged.connect(self._update_source_actions)
        self.pick_source_button.clicked.connect(self._begin_source_pick)
        self.cancel_pick_button.clicked.connect(self._cancel_source_pick)
        self.show_source_button.clicked.connect(self._select_source_in_view)
        self.apply_button.clicked.connect(self._apply)

    def _set_status(self, text: str, state: str = "info") -> None:
        """Update task feedback using the shared semantic status treatment.

        Args:
            text: User-facing explanation of the current target state.
            state: Semantic presentation state such as info, warning, or error.
        """
        _set_status_label(self.status, text, state=state)

    def _find_target(self) -> _DrapeTargetFeature | None:
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

    def _preview_status(self, *_args: _QtSignalValue) -> None:
        """Explain that changed controls remain unapplied until Apply or OK.

        Args:
            _args: Optional values provided by Qt signal callbacks.
        """
        if self._loading:
            return
        self._set_status(
            "Staged target edits. Apply & Refresh commits the collision settings now; "
            "Cancel closes without applying further edits.",
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
        normalized_state = state.casefold()
        if normalized_state in {"invalid", "unassigned", "stale", "blocked", "error"}:
            semantic_state = "error"
        elif normalized_state == "ready":
            semantic_state = "success"
        else:
            semantic_state = "info"
        self._set_status(message, state=semantic_state)

    def _selected_source(self) -> FreeCADDocumentObjectProtocol | None:
        """Return the currently selected collision source.

        Returns:
            The selected source object, or None when the selection is invalid.
        """
        index = self.source.currentIndex()
        if index < 0 or index >= len(self._source_objects):
            return None
        return self._source_objects[index]

    def _update_source_actions(self, _index: int | None = None) -> None:
        """Enable viewport and apply actions only when their prerequisites exist.

        Args:
            _index: Optional combo-box index emitted by Qt after source selection.
        """
        selected = self._selected_source() is not None
        target_available = self.target is not None
        self.show_source_button.setEnabled(selected)
        self.apply_button.setEnabled(target_available and selected)
        self.pick_source_button.setEnabled(
            target_available
            and self.doc is not None
            and bool(self._source_objects)
            and self._source_picker is None
        )

    def _select_source_object(self, source: FreeCADDocumentObjectProtocol) -> bool:
        """Synchronize a viewport-picked object with the source/provider controls.

        Args:
            source: Existing document object selected in the viewport.

        Returns:
            True when the source is present in the current document inventory.
        """
        source_name = str(getattr(source, "Name", ""))
        index = next(
            (
                position
                for position, candidate in enumerate(self._source_objects)
                if candidate is source or (
                    source_name and str(getattr(candidate, "Name", "")) == source_name
                )
            ),
            -1,
        )
        if index < 0:
            return False
        provider = (
            "Mannequin"
            if str(getattr(source, "AvatarType", "")) == "ClothAvatar"
            else "FreeCAD Geometry"
        )
        if str(self.target_type.currentText()) != provider:
            self.target_type.setCurrentText(provider)
            # Changing provider refreshes the inventory; resolve the stable object name again.
            source_name = str(getattr(source, "Name", ""))
            index = next(
                (
                    position
                    for position, candidate in enumerate(self._source_objects)
                    if candidate is source or (
                        source_name and str(getattr(candidate, "Name", "")) == source_name
                    )
                ),
                -1,
            )
        if index < 0:
            return False
        self.source.setCurrentIndex(index)
        self._update_source_actions()
        return True

    def _begin_source_pick(self) -> None:
        """Arm a one-shot FreeCAD selection observer for viewport source picking."""
        if self.target is None or self.doc is None:
            self._set_status(
                "Create a Drape Target before picking a collision source.",
                state="warning",
            )
            return
        if self._source_picker is not None:
            return
        try:
            self._source_picker = _ViewportSourcePicker(self)
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            self._source_picker = None
            self._set_status(
                f"Viewport picking is unavailable — {exc}. Use the source selector instead.",
                state="warning",
            )
            return
        self.pick_source_button.setEnabled(False)
        self.cancel_pick_button.setVisible(True)
        self._set_status(
            "Pick a mannequin, shape, or mesh in the 3D view. "
            "The source is staged; use Apply & Refresh to rebuild collision geometry.",
            state="info",
        )

    def _cancel_source_pick(self, *, update_status: bool = True) -> None:
        """Disarm the viewport picker without changing the persistent target.

        Args:
            update_status: Whether to show the cancellation feedback in the panel.
        """
        picker = self._source_picker
        if picker is None:
            return
        picker.dispose()
        if update_status:
            self._set_status("Viewport source pick cancelled; target unchanged.", state="info")

    def _select_source_in_view(self) -> bool:
        """Highlight the current collision source using FreeCAD's native selection.

        Returns:
            True when a valid source was selected in the active 3D view.
        """
        source = self._selected_source()
        if source is None:
            self._set_status("Select a collision source first.", state="warning")
            return False
        try:
            self.Gui.Selection.clearSelection()
            self.Gui.Selection.addSelection(source)
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            self._set_status(f"Could not select the source in the 3D view — {exc}.", state="error")
            return False
        label = str(getattr(source, "Label", getattr(source, "Name", "collision source")))
        self._set_status(
            f"Selected {label} in the 3D view. This highlights the source "
            "without moving the camera.",
            state="info",
        )
        return True

    def _apply(self, *, assign_target: _AssignDrapeTarget | None = None) -> bool:
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
        if self._source_picker is not None:
            self._cancel_source_pick(update_status=False)
        accepted = self._apply()
        return accepted

    def reject(self) -> bool:
        """Close the task panel without applying staged control values.

        Returns:
            True to allow FreeCAD to close the task panel.
        """
        if self._source_picker is not None:
            self._cancel_source_pick(update_status=False)
        gui = cast("_FreeCADGui", self.Gui)
        if gui.activeDocument() and gui.Control.activeDialog():
            gui.Control.closeDialog()
        return True

    @staticmethod
    def _standard_buttons() -> int:
        """Return the native OK and Cancel button flags for the task panel.

        Returns:
            The combined Qt button flags used to accept or cancel editing.
        """
        _app_module, _gui_module, qt_widgets = _modules()
        return int(qt_widgets.QDialogButtonBox.Ok | qt_widgets.QDialogButtonBox.Cancel)

    def __getattr__(self, name: str) -> Callable[[], int]:
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


def show_drape_target_task(target: _DrapeTargetFeature | None = None) -> DrapeTargetTaskPanel:
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
