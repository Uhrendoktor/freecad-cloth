"""FreeCAD task-panel frontend for the target-neutral drape object.

The persistent DrapeTarget document object remains authoritative.  This panel
only stages target selection and collision settings until the user applies or
cancels the edit, following normal FreeCAD task-panel conventions.
"""


def _modules():
    import FreeCAD as App
    import FreeCADGui as Gui
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    return App, Gui, QtWidgets


class DrapeTargetTaskPanel:
    """CLO-like grouped editor for a persistent DrapeTarget."""

    PRESETS = (
        ("Preview", 2.5),
        ("Normal", 1.0),
        ("Final", 0.35),
    )

    def __init__(self, target=None):
        App, Gui, QtWidgets = _modules()
        self.App, self.Gui = App, Gui
        self.doc = App.ActiveDocument
        self.target = target or self._find_target()
        self.form = QtWidgets.QWidget()
        self.form.setObjectName("ClothDrapeTargetTaskPanel")
        root = QtWidgets.QVBoxLayout(self.form)

        title = QtWidgets.QLabel("Drape Target")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        root.addWidget(title)

        source_group = QtWidgets.QGroupBox("Collision object")
        source_layout = QtWidgets.QFormLayout(source_group)
        self.target_type = QtWidgets.QComboBox()
        self.target_type.addItems(("Mannequin", "FreeCAD Geometry"))
        self.source = QtWidgets.QComboBox()
        self._source_objects = []
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
        root.addWidget(self.status)

        controls = QtWidgets.QHBoxLayout()
        self.apply_button = QtWidgets.QPushButton("Apply & Refresh")
        self.cancel_button = QtWidgets.QPushButton("Cancel")
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

    def _find_target(self):
        if self.doc is None:
            return None
        return self.doc.getObject("DrapeTarget")

    def _populate_sources(self):
        self._source_objects = []
        self.source.clear()
        if self.doc is None:
            return
        for obj in self.doc.Objects:
            if obj is self.target:
                continue
            if getattr(obj, "AvatarType", "") == "ClothAvatar" or hasattr(obj, "Shape") or hasattr(obj, "Mesh"):
                self._source_objects.append(obj)
                self.source.addItem(str(getattr(obj, "Label", getattr(obj, "Name", ""))))

    def _load(self):
        if self.target is None:
            self.status.setText("Create a Drape Target first, or select a mannequin/FreeCAD object.")
            self.apply_button.setEnabled(False)
            return
        self._loading = True
        self.target_type.setCurrentText(str(getattr(self.target, "TargetType", "FreeCAD Geometry")))
        source_obj = getattr(self.target, "SourceObject", None)
        source_index = next((i for i, obj in enumerate(self._source_objects) if obj is source_obj), -1)
        if source_index >= 0:
            self.source.setCurrentIndex(source_index)
        self.deflection.setValue(float(getattr(self.target, "CollisionDeflection", 1.0)))
        self.thickness.setValue(float(getattr(self.target, "CollisionThickness", 2.0)))
        self.enabled.setChecked(bool(getattr(self.target, "Enabled", True)))
        self._select_nearest_preset(self.deflection.value())
        self._loading = False
        self._refresh_status()

    def _provider_changed(self, _value):
        if self._loading:
            return
        self._populate_sources()
        self._preview_status()

    def _select_nearest_preset(self, value):
        nearest = min(range(len(self.PRESETS)), key=lambda i: abs(self.PRESETS[i][1] - value))
        self.preset.blockSignals(True)
        self.preset.setCurrentIndex(nearest)
        self.preset.blockSignals(False)

    def _preset_changed(self, name):
        if self._loading:
            return
        for preset_name, value in self.PRESETS:
            if preset_name == name:
                self.deflection.blockSignals(True)
                self.deflection.setValue(value)
                self.deflection.blockSignals(False)
                break
        self._preview_status()

    def _preview_status(self, *_args):
        if self._loading:
            return
        self.status.setText("Staged target edits. Apply & Refresh to rebuild collision geometry; Cancel leaves the document unchanged.")

    def _refresh_status(self):
        if self.target is None:
            return
        state = str(getattr(self.target, "TargetStatus", "unbuilt"))
        reason = str(getattr(self.target, "InvalidationReason", ""))
        message = "Target status: %s" % state
        if reason:
            message += " — " + reason
        self.status.setText(message)

    def _selected_source(self):
        index = self.source.currentIndex()
        if index < 0 or index >= len(self._source_objects):
            return None
        return self._source_objects[index]

    def _apply(self):
        if self.target is None:
            return False
        source = self._selected_source()
        target_type = str(self.target_type.currentText())
        if source is None:
            self.status.setText("Select a collision object before applying the target.")
            return False
        from DrapeTarget import assign_drape_target
        self.target.CollisionDeflection = self.deflection.value()
        self.target.CollisionThickness = self.thickness.value()
        self.target.Enabled = self.enabled.isChecked()
        assign_drape_target(self.target, source, target_type)
        if self.doc is not None:
            self.doc.recompute()
        self._refresh_status()
        return True

    def accept(self):
        return self._apply()

    def reject(self):
        if self.Gui.activeDocument() and self.Gui.Control.activeDialog():
            self.Gui.Control.closeDialog()
        return True

    def getStandardButtons(self):
        _, _, QtWidgets = _modules()
        return QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel


def show_drape_target_task(target=None):
    """Open the native FreeCAD task panel for a DrapeTarget."""
    _App, Gui, _QtWidgets = _modules()
    panel = DrapeTargetTaskPanel(target)
    Gui.Control.showDialog(panel)
    return panel
