"""FreeCAD task-panel frontend for the parametric Cloth mannequin.

Anthropometric edits are staged in the UI and applied atomically through the
existing AvatarCommands rebuild path. AvatarParameters remains authoritative
for validation and AvatarService remains the solver-neutral downstream API.
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
    """CLO-like grouped mannequin editor with staged Apply/Cancel semantics."""

    PROPERTY_MAP = {
        "height": "Height", "neck": "Neck", "shoulder": "Shoulder",
        "chest": "Chest", "underbust": "Underbust", "waist": "Waist",
        "high_hip": "High_Hip", "hip": "Hip", "upper_arm": "Upper_Arm",
        "elbow": "Elbow", "wrist": "Wrist", "thigh": "Thigh",
        "knee": "Knee", "calf": "Calf", "ankle": "Ankle",
        "inseam": "Inseam", "torso": "Torso", "front_waist": "Front_Waist",
        "back_waist": "Back_Waist",
    }
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
        self.pose.setToolTip("Choose the saved fitting pose.")
        pose_layout.addRow("Preset", self.pose)
        content_layout.addWidget(pose)

        display = QtWidgets.QGroupBox("Display")
        display_layout = QtWidgets.QFormLayout(display)
        self.skin_offset = QtWidgets.QDoubleSpinBox()
        self.skin_offset.setRange(0.0, 50.0)
        self.skin_offset.setDecimals(1)
        self.skin_offset.setSuffix(" mm")
        self.show_measurements = QtWidgets.QCheckBox("Show measurement landmarks")
        self.show_measurements.setToolTip("Show the stable named landmarks stored by the mannequin.")
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
        self.apply_button = QtWidgets.QPushButton("Apply & Rebuild")
        self.rebuild_button = QtWidgets.QPushButton("Rebuild")
        self.fit_button = QtWidgets.QPushButton("Fit view")
        controls.addWidget(self.apply_button)
        controls.addWidget(self.rebuild_button)
        controls.addWidget(self.fit_button)
        root.addLayout(controls)

        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        self._dirty = False
        self._load()
        for box in self._boxes.values():
            box.valueChanged.connect(self._staged_changed)
        self.pose.currentTextChanged.connect(self._staged_changed)
        self.skin_offset.valueChanged.connect(self._staged_changed)
        self.show_measurements.toggled.connect(self._landmarks_visibility_changed)
        self.apply_button.clicked.connect(self._apply)
        self.rebuild_button.clicked.connect(self._apply)
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
            box.setToolTip("Staged anthropometric value in millimetres.")
            layout.addRow(label, box)
            self._boxes[key] = box
        parent.addWidget(group)

    def _load(self):
        if self.avatar is None:
            self.status.setText("Create a Cloth Human Mannequin first.")
            self.apply_button.setEnabled(False)
            self.rebuild_button.setEnabled(False)
            self.fit_button.setEnabled(False)
            return
        for key, box in self._boxes.items():
            box.blockSignals(True)
            box.setValue(float(getattr(self.avatar, self.PROPERTY_MAP[key])))
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

    def _staged_changed(self):
        self._dirty = True
        self._refresh_status("Unsaved mannequin edits are staged. Apply & Rebuild to update the body.")

    def _staged_parameters(self):
        from AvatarModel import AvatarParameters, Pose
        values = {key: box.value() for key, box in self._boxes.items()}
        return AvatarParameters(values, self.skin_offset.value(), Pose(str(self.pose.currentText())))

    def _apply(self):
        if self.avatar is None:
            return False
        params = self._staged_parameters()
        for key, property_name in self.PROPERTY_MAP.items():
            setattr(self.avatar, property_name, params.measurements[key])
        self.avatar.PosePreset = params.pose.preset
        self.avatar.SkinOffset = params.skin_offset
        self._dirty = False
        self._rebuild_geometry()
        self._update_landmarks()
        self._refresh_status("Mannequin rebuilt from applied persistent parameters.")
        self._fit_view()
        return True

    def _rebuild_geometry(self):
        from AvatarCommands import rebuild_avatar
        rebuild_avatar()

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
        suffix = " | staged changes" if self._dirty else ""
        self.status.setText(message or "Avatar status: %s | pose: %s%s" % (
            str(getattr(self.avatar, "AvatarStatus", "Unknown")),
            str(getattr(self.avatar, "PosePreset", "standing")), suffix,
        ))

    def _fit_view(self):
        if self.Gui.activeDocument():
            self.Gui.activeDocument().activeView().fitAll()

    def accept(self):
        return self._apply()

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
