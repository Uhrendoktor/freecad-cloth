"""FreeCAD task-panel frontend for the parametric Cloth mannequin.

The panel is deliberately thin: anthropometric values remain persistent
FreeCAD properties and AvatarModel/AvatarCommands remain authoritative for
validation and deterministic geometry generation.
"""


def _modules():
    import FreeCAD as App
    import FreeCADGui as Gui
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    return App, Gui, QtWidgets


class AvatarTaskPanel:
    """Grouped CLO-like mannequin controls backed by the FreeCAD object."""

    BODY = (
        ("height", "Height"), ("neck", "Neck circumference"),
        ("shoulder", "Shoulder breadth"), ("chest", "Chest / bust"),
        ("underbust", "Underbust"), ("waist", "Waist"),
        ("high_hip", "High hip"), ("hip", "Hip"),
        ("upper_arm", "Upper arm"), ("elbow", "Elbow"),
        ("wrist", "Wrist"), ("thigh", "Thigh"),
        ("knee", "Knee"), ("calf", "Calf"), ("ankle", "Ankle"),
    )
    PROPORTIONS = (
        ("inseam", "Inseam"), ("torso", "Torso length"),
        ("front_waist", "Front waist length"), ("back_waist", "Back waist length"),
    )

    def __init__(self, avatar=None):
        App, Gui, QtWidgets = _modules()
        self.App, self.Gui = App, Gui
        self.avatar = avatar or self._find_avatar()
        self.form = QtWidgets.QWidget()
        self.form.setObjectName("ClothAvatarTaskPanel")
        root = QtWidgets.QVBoxLayout(self.form)

        title = QtWidgets.QLabel("Parametric Human Mannequin")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        root.addWidget(title)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        content = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content)
        self._boxes = {}
        self._add_measurement_group(content_layout, "Body measurements", self.BODY)
        self._add_measurement_group(content_layout, "Proportions", self.PROPORTIONS)

        pose = QtWidgets.QGroupBox("Pose")
        pose_layout = QtWidgets.QFormLayout(pose)
        self.pose = QtWidgets.QComboBox()
        self.pose.addItems(("standing", "sewing", "sitting"))
        self.pose.setToolTip("Choose the saved fitting pose; geometry is regenerated deterministically.")
        pose_layout.addRow("Preset", self.pose)
        content_layout.addWidget(pose)

        display = QtWidgets.QGroupBox("Display")
        display_layout = QtWidgets.QFormLayout(display)
        self.skin_offset = QtWidgets.QDoubleSpinBox()
        self.skin_offset.setRange(0.0, 50.0)
        self.skin_offset.setDecimals(1)
        self.skin_offset.setSuffix(" mm")
        self.show_measurements = QtWidgets.QCheckBox("Show measurement landmarks")
        self.show_measurements.setToolTip("Display the named mannequin landmarks in the panel status area.")
        display_layout.addRow("Collision / skin offset", self.skin_offset)
        display_layout.addRow(self.show_measurements)
        content_layout.addWidget(display)

        self.landmarks = QtWidgets.QLabel()
        self.landmarks.setWordWrap(True)
        self.landmarks.setObjectName("ClothAvatarLandmarks")
        content_layout.addWidget(self.landmarks)
        content_layout.addStretch(1)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        controls = QtWidgets.QHBoxLayout()
        self.rebuild_button = QtWidgets.QPushButton("Rebuild")
        self.fit_button = QtWidgets.QPushButton("Fit view")
        controls.addWidget(self.rebuild_button)
        controls.addWidget(self.fit_button)
        root.addLayout(controls)

        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        self._load()
        for box in self._boxes.values():
            box.valueChanged.connect(self._measurement_changed)
        self.pose.currentTextChanged.connect(self._pose_changed)
        self.skin_offset.valueChanged.connect(self._offset_changed)
        self.show_measurements.toggled.connect(self._landmarks_visibility_changed)
        self.rebuild_button.clicked.connect(self._rebuild)
        self.fit_button.clicked.connect(self._fit_view)

    def _find_avatar(self):
        doc = self.App.ActiveDocument
        if doc is None:
            return None
        return next((o for o in doc.Objects if getattr(o, "AvatarType", "") == "ClothAvatar"), None)

    def _add_measurement_group(self, parent, title, fields):
        _, _, QtWidgets = _modules()
        group = QtWidgets.QGroupBox(title)
        layout = QtWidgets.QFormLayout(group)
        for key, label in fields:
            box = QtWidgets.QDoubleSpinBox()
            box.setRange(1.0, 3000.0)
            box.setDecimals(1)
            box.setSuffix(" mm")
            box.setToolTip("Persistent anthropometric measurement in millimetres.")
            layout.addRow(label, box)
            self._boxes[key] = box
        parent.addWidget(group)

    def _load(self):
        if self.avatar is None:
            self.status.setText("Create a Cloth Human Mannequin first.")
            self.rebuild_button.setEnabled(False)
            self.fit_button.setEnabled(False)
            return
        for key, box in self._boxes.items():
            box.blockSignals(True)
            box.setValue(float(getattr(self.avatar, key.title())))
            box.blockSignals(False)
        self.pose.blockSignals(True)
        self.pose.setCurrentText(str(getattr(self.avatar, "PosePreset", "standing")))
        self.pose.blockSignals(False)
        self.skin_offset.blockSignals(True)
        self.skin_offset.setValue(float(getattr(self.avatar, "SkinOffset", 3.0)))
        self.skin_offset.blockSignals(False)
        self.show_measurements.setChecked(True)
        self._update_landmarks()
        self._refresh_status()

    def _rebuild(self):
        if self.avatar is None:
            return
        from AvatarCommands import rebuild_avatar
        rebuild_avatar()
        self._update_landmarks()
        self._refresh_status("Mannequin rebuilt from persistent parameters.")
        self._fit_view()

    def _measurement_changed(self):
        if self.avatar is None:
            return
        for key, box in self._boxes.items():
            setattr(self.avatar, key.title(), box.value())
        self._rebuild()

    def _pose_changed(self, value):
        if self.avatar is None or not value:
            return
        self.avatar.PosePreset = str(value)
        self._rebuild()

    def _offset_changed(self, value):
        if self.avatar is None:
            return
        self.avatar.SkinOffset = float(value)
        self._rebuild()

    def _update_landmarks(self):
        if self.avatar is None or not self.show_measurements.isChecked():
            self.landmarks.setText("")
            return
        entries = []
        for item in getattr(self.avatar, "Landmarks", []) or []:
            name, coords = str(item).split("|", 1)
            entries.append("%s: (%s)" % (name.replace("_", " ").title(), coords))
        self.landmarks.setText("<b>Landmarks</b><br>" + "<br>".join(entries))

    def _landmarks_visibility_changed(self, _checked):
        self._update_landmarks()

    def _refresh_status(self, message=None):
        if self.avatar is None:
            self.status.setText(message or "No mannequin selected.")
            return
        self.status.setText(message or "Avatar status: %s | pose: %s" % (
            str(getattr(self.avatar, "AvatarStatus", "Unknown")),
            str(getattr(self.avatar, "PosePreset", "standing")),
        ))

    def _fit_view(self):
        if self.Gui.activeDocument():
            self.Gui.activeDocument().activeView().fitAll()

    def accept(self):
        self._rebuild()
        return True

    def reject(self):
        if self.Gui.activeDocument() and self.Gui.Control.activeDialog():
            self.Gui.Control.closeDialog()
        return True

    def getStandardButtons(self):
        _, _, QtWidgets = _modules()
        return QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel


def show_avatar_task(avatar=None):
    """Open the native FreeCAD task panel for a mannequin."""
    _App, Gui, _QtWidgets = _modules()
    panel = AvatarTaskPanel(avatar)
    Gui.Control.showDialog(panel)
    return panel
