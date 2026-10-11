"""FreeCAD task-panel frontend for the parametric Cloth mannequin.

Anthropometric edits are staged in the UI and applied atomically through the
existing AvatarCommands rebuild path. AvatarParameters remains authoritative
for validation and AvatarService remains the solver-neutral downstream API.
"""

import contextlib


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
        "height": "Height",
        "neck": "Neck",
        "shoulder": "Shoulder",
        "chest": "Chest",
        "underbust": "Underbust",
        "waist": "Waist",
        "high_hip": "High_Hip",
        "hip": "Hip",
        "upper_arm": "Upper_Arm",
        "elbow": "Elbow",
        "wrist": "Wrist",
        "thigh": "Thigh",
        "knee": "Knee",
        "calf": "Calf",
        "ankle": "Ankle",
        "inseam": "Inseam",
        "torso": "Torso",
        "front_waist": "Front_Waist",
        "back_waist": "Back_Waist",
    }
    SHAPE_PROPERTY_MAP = {"gender": "GenderBlend", "breast_size": "BreastSize"}
    BODY = (
        ("height", "Height"),
        ("neck", "Neck circumference"),
        ("shoulder", "Shoulder breadth"),
        ("chest", "Chest / bust"),
        ("underbust", "Underbust"),
        ("waist", "Waist"),
        ("high_hip", "High hip"),
        ("hip", "Hip"),
        ("upper_arm", "Upper arm"),
        ("elbow", "Elbow"),
        ("wrist", "Wrist"),
        ("thigh", "Thigh"),
        ("knee", "Knee"),
        ("calf", "Calf"),
        ("ankle", "Ankle"),
    )
    PROPORTIONS = (
        ("inseam", "Inseam"),
        ("torso", "Torso length"),
        ("front_waist", "Front waist length"),
        ("back_waist", "Back waist length"),
    )
    POSE_FIELDS = (
        ("left_arm_angle", "Left arm"),
        ("right_arm_angle", "Right arm"),
        ("left_elbow_angle", "Left elbow bend"),
        ("right_elbow_angle", "Right elbow bend"),
    )
    PROVIDERS = (
        ("makehuman-hm08", "MakeHuman HM08 humanoid mesh"),
        (
            "freecad-geometry",
            "Imported surface only; no skeleton, skin weights, or animation are imported",
        ),
    )

    def __init__(self, avatar=None):
        App, Gui, QtWidgets = _modules()
        self.App, self.Gui = App, Gui
        self.avatar = avatar or self._find_avatar()
        self.form = QtWidgets.QWidget()
        self.form.setObjectName("ClothAvatarTaskPanel")
        root = QtWidgets.QVBoxLayout(self.form)

        title_row = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Parametric Human Mannequin")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        title_row.addWidget(title)
        title_row.addStretch(1)
        self.dimension_gizmo_toggle = QtWidgets.QToolButton()
        self.dimension_gizmo_toggle.setText("3D Dimensions")
        self.dimension_gizmo_toggle.setCheckable(True)
        self.dimension_gizmo_toggle.setChecked(True)
        self.dimension_gizmo_toggle.setToolTip(
            "Show transient viewport handles for height, shoulder breadth, chest, waist and hip. "
            "Drag a handle to stage a dimension; Apply & Rebuild commits it."
        )
        title_row.addWidget(self.dimension_gizmo_toggle)
        self.pose_mode_button = QtWidgets.QPushButton("3D Pose Mode…")
        self.pose_mode_button.setToolTip(
            "Open the focused mannequin posing editor. Use the 3D rotation gizmo instead of typing joint angles."
        )
        title_row.addWidget(self.pose_mode_button)
        root.addLayout(title_row)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        content = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content)
        self._boxes = {}
        self._pose_boxes = {}
        self._add_shape_group(content_layout)
        self._add_measurement_group(content_layout, "Body measurements", self.BODY)
        self._add_measurement_group(content_layout, "Proportions", self.PROPORTIONS)

        provider = QtWidgets.QGroupBox("Avatar provider")
        provider_layout = QtWidgets.QVBoxLayout(provider)
        self._provider_ids = [key for key, _label in self.PROVIDERS]
        self.provider_group = QtWidgets.QButtonGroup(self.form)
        self.provider_group.setExclusive(True)
        self.provider_buttons = {}
        provider_row = QtWidgets.QHBoxLayout()
        for key, label in self.PROVIDERS:
            button = QtWidgets.QToolButton()
            button.setText("MakeHuman" if key == "makehuman-hm08" else "FreeCAD geometry")
            button.setCheckable(True)
            button.setAutoRaise(True)
            button.setToolTip(label)
            self.provider_group.addButton(button)
            self.provider_buttons[key] = button
            provider_row.addWidget(button)
            button.clicked.connect(lambda checked=False, value=key: self._provider_changed(value))
        provider_row.addStretch(1)
        provider_layout.addLayout(provider_row)
        self.provider_source = QtWidgets.QPushButton("Use selected FreeCAD object")
        self.provider_source.setToolTip(
            "Select an imported body or mesh in the 3D view. This uses its surface only; "
            "the source skeleton, skin weights, and animation are not imported."
        )
        self.provider_source_label = QtWidgets.QLabel("Source: none")
        self.provider_source_label.setWordWrap(True)
        provider_layout.addWidget(self.provider_source)
        provider_layout.addWidget(self.provider_source_label)
        content_layout.addWidget(provider)

        pose = QtWidgets.QGroupBox("Pose")
        pose_layout = QtWidgets.QFormLayout(pose)
        self.pose = QtWidgets.QComboBox()
        self.pose.addItems(("standing", "sewing", "sitting", "t_pose"))
        self.pose.setToolTip("Choose the saved fitting pose.")
        pose_layout.addRow("Preset", self.pose)
        for key, label in self.POSE_FIELDS:
            box = QtWidgets.QDoubleSpinBox()
            box.setRange(-90.0, 90.0)
            box.setDecimals(1)
            box.setSuffix(" deg")
            box.setToolTip("Staged joint angle. Preset changes remain editable.")
            pose_layout.addRow(label, box)
            self._pose_boxes[key] = box
        content_layout.addWidget(pose)
        self._legacy_pose_group = pose
        pose.setVisible(False)

        skeleton = QtWidgets.QGroupBox("Skeleton pose")
        skeleton_layout = QtWidgets.QFormLayout(skeleton)
        hint = QtWidgets.QLabel(
            "Manual FK. Edit a joint in mannequin space; child bones follow the authored skeleton."
        )
        hint.setWordWrap(True)
        skeleton_layout.addRow(hint)
        self.skeleton_joint = QtWidgets.QComboBox()
        from freecad_cloth.avatar.SkeletonPose import CONTROLLABLE_JOINTS

        for bone, label in CONTROLLABLE_JOINTS:
            self.skeleton_joint.addItem(label, bone)
        self.skeleton_joint.setToolTip(
            "Select a MakeHuman-authored joint and edit its Euler rotation."
        )
        skeleton_layout.addRow("Joint", self.skeleton_joint)
        self.skeleton_x = QtWidgets.QDoubleSpinBox()
        self.skeleton_y = QtWidgets.QDoubleSpinBox()
        self.skeleton_z = QtWidgets.QDoubleSpinBox()
        for label, box in (
            ("X rotation", self.skeleton_x),
            ("Y rotation", self.skeleton_y),
            ("Z rotation", self.skeleton_z),
        ):
            box.setRange(-180.0, 180.0)
            box.setDecimals(1)
            box.setSuffix(" deg")
            box.setToolTip("Staged joint rotation in degrees.")
            skeleton_layout.addRow(label, box)
        self.skeleton_symmetry = QtWidgets.QCheckBox("Symmetry")
        self.skeleton_symmetry.setChecked(True)
        self.skeleton_symmetry.setToolTip(
            "Mirror bilateral joint edits across the mannequin center plane."
        )
        skeleton_layout.addRow(self.skeleton_symmetry)
        self.reset_skeleton_button = QtWidgets.QPushButton("Reset skeleton pose")
        self.reset_skeleton_button.setToolTip(
            "Clear manual joint rotations and return to the preset baseline."
        )
        skeleton_layout.addRow(self.reset_skeleton_button)
        content_layout.addWidget(skeleton)
        self._legacy_skeleton_group = skeleton
        skeleton.setVisible(False)

        display = QtWidgets.QGroupBox("Display")
        display_layout = QtWidgets.QFormLayout(display)
        self.skin_offset = QtWidgets.QDoubleSpinBox()
        self.skin_offset.setRange(0.0, 50.0)
        self.skin_offset.setDecimals(1)
        self.skin_offset.setSuffix(" mm")
        self.show_measurements = QtWidgets.QCheckBox("Show measurement landmarks")
        self.show_measurements.setToolTip(
            "Show the stable named landmarks stored by the mannequin."
        )
        display_layout.addRow("Collision / skin offset", self.skin_offset)
        display_layout.addRow(self.show_measurements)
        content_layout.addWidget(display)

        arrangement = QtWidgets.QGroupBox("Arrangement points")
        arrangement_layout = QtWidgets.QVBoxLayout(arrangement)
        self.arrangement_points = QtWidgets.QListWidget()
        self.arrangement_points.setToolTip(
            "Persistent local fitting points used as a foundation for garment placement."
        )
        self.arrangement_points.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        arrangement_layout.addWidget(self.arrangement_points)
        content_layout.addWidget(arrangement)

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

        self._loading = True
        self._dirty = False
        self._staged_joint_rotations = {}
        try:
            self._load()
        finally:
            self._loading = False
        for box in self._boxes.values():
            box.valueChanged.connect(self._staged_changed)
        for box in self._pose_boxes.values():
            box.valueChanged.connect(self._staged_changed)
        self.pose.currentTextChanged.connect(self._preset_changed)
        self.skeleton_joint.currentIndexChanged.connect(self._load_selected_joint)
        for box in (self.skeleton_x, self.skeleton_y, self.skeleton_z):
            box.valueChanged.connect(self._joint_changed)
        self.skeleton_symmetry.toggled.connect(self._symmetry_changed)
        self.reset_skeleton_button.clicked.connect(self._reset_skeleton_pose)
        self.provider_source.clicked.connect(self._use_selected_provider_source)
        self.skin_offset.valueChanged.connect(self._staged_changed)
        self.show_measurements.toggled.connect(self._landmarks_visibility_changed)
        self.apply_button.clicked.connect(self._apply)
        self.rebuild_button.clicked.connect(self._apply)
        self.fit_button.clicked.connect(self._fit_view)
        self.pose_mode_button.clicked.connect(self._open_pose_mode)
        self.gender_slider.valueChanged.connect(self._shape_changed)
        self.breast_slider.valueChanged.connect(self._shape_changed)
        self.dimension_gizmo_toggle.toggled.connect(self._toggle_dimension_gizmo)
        self._dimension_controller = None
        self._toggle_dimension_gizmo(self.dimension_gizmo_toggle.isChecked())

    def _open_pose_mode(self):
        if self.avatar is None:
            return
        with contextlib.suppress(AttributeError, RuntimeError):
            self.Gui.Control.closeDialog()
        from freecad_cloth.avatar.AvatarCommands import pose_avatar

        pose_avatar(self.avatar)

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

    def _add_shape_group(self, parent):
        """Build compact macro-shape controls; precise dimensions stay below."""
        _, _, QtWidgets = _modules()
        try:
            from PySide import QtCore
        except ImportError:
            from PySide2 import QtCore

        group = QtWidgets.QGroupBox("Body shape")
        layout = QtWidgets.QFormLayout(group)

        gender_row = QtWidgets.QHBoxLayout()
        gender_row.addWidget(QtWidgets.QLabel("Feminine"))
        self.gender_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.gender_slider.setRange(0, 100)
        self.gender_slider.setSingleStep(1)
        self.gender_slider.setPageStep(10)
        self.gender_slider.setToolTip(
            "Blend body proportions from feminine (0) through neutral (50) to masculine (100)."
        )
        gender_row.addWidget(self.gender_slider, 1)
        gender_row.addWidget(QtWidgets.QLabel("Masculine"))
        gender_container = QtWidgets.QWidget()
        gender_container.setLayout(gender_row)
        self.gender_value = QtWidgets.QLabel("Neutral")
        self.gender_value.setMinimumWidth(90)
        gender_value_row = QtWidgets.QHBoxLayout()
        gender_value_row.addWidget(gender_container, 1)
        gender_value_row.addWidget(self.gender_value)
        gender_wrapper = QtWidgets.QWidget()
        gender_wrapper.setLayout(gender_value_row)
        layout.addRow("Gender blend", gender_wrapper)

        breast_row = QtWidgets.QHBoxLayout()
        breast_row.addWidget(QtWidgets.QLabel("Less"))
        self.breast_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.breast_slider.setRange(0, 100)
        self.breast_slider.setSingleStep(1)
        self.breast_slider.setPageStep(10)
        self.breast_slider.setToolTip(
            "Stage additional breast projection from the neutral base shape (0–100%)."
        )
        breast_row.addWidget(self.breast_slider, 1)
        breast_row.addWidget(QtWidgets.QLabel("More"))
        breast_container = QtWidgets.QWidget()
        breast_container.setLayout(breast_row)
        self.breast_value = QtWidgets.QLabel("0%")
        self.breast_value.setMinimumWidth(90)
        breast_value_row = QtWidgets.QHBoxLayout()
        breast_value_row.addWidget(breast_container, 1)
        breast_value_row.addWidget(self.breast_value)
        breast_wrapper = QtWidgets.QWidget()
        breast_wrapper.setLayout(breast_value_row)
        layout.addRow("Breast fullness", breast_wrapper)
        parent.addWidget(group)
        self.shape_group = group

    def _load(self):
        if self.avatar is None:
            self.status.setText("Create a Cloth Human Mannequin first.")
            self.apply_button.setEnabled(False)
            self.rebuild_button.setEnabled(False)
            self.fit_button.setEnabled(False)
            for button in self.provider_buttons.values():
                button.setEnabled(False)
            self.provider_source.setEnabled(False)
            return
        for key, box in self._boxes.items():
            box.blockSignals(True)
            box.setValue(float(getattr(self.avatar, self.PROPERTY_MAP[key])))
            box.blockSignals(False)
        self.gender_slider.blockSignals(True)
        self.gender_slider.setValue(round(100.0 * float(getattr(self.avatar, "GenderBlend", 0.5))) )
        self.gender_slider.blockSignals(False)
        self.breast_slider.blockSignals(True)
        self.breast_slider.setValue(round(100.0 * float(getattr(self.avatar, "BreastSize", 0.0))))
        self.breast_slider.blockSignals(False)
        self._update_shape_labels()
        current_provider = str(getattr(self.avatar, "AvatarProviderId", "makehuman-hm08"))
        if current_provider not in self.provider_buttons:
            current_provider = "makehuman-hm08"
        self.provider_buttons[current_provider].setChecked(True)
        self._refresh_provider_source()
        self.pose.blockSignals(True)
        self.pose.setCurrentText(str(getattr(self.avatar, "PosePreset", "standing")))
        self.pose.blockSignals(False)
        from freecad_cloth.avatar.AvatarModel import Pose

        pose_defaults = Pose(str(self.pose.currentText()))
        pose_values = {
            "left_arm_angle": float(pose_defaults.left_arm_angle),
            "right_arm_angle": float(pose_defaults.right_arm_angle),
            "left_elbow_angle": float(pose_defaults.left_elbow_angle),
            "right_elbow_angle": float(pose_defaults.right_elbow_angle),
        }
        for key, box in self._pose_boxes.items():
            box.blockSignals(True)
            box.setValue(float(getattr(self.avatar, self._pose_property(key), pose_values[key])))
            box.blockSignals(False)
        self.skin_offset.blockSignals(True)
        self.skin_offset.setValue(float(getattr(self.avatar, "SkinOffset", 3.0)))
        self.skin_offset.blockSignals(False)
        self._load_skeleton_pose()
        self.show_measurements.setChecked(bool(getattr(self.avatar, "Landmarks", [])))
        self._update_arrangement_points()
        self._update_landmarks()
        self._refresh_status()

    @staticmethod
    def _pose_property(key):
        return {
            "left_arm_angle": "LeftArmAngle",
            "right_arm_angle": "RightArmAngle",
            "left_elbow_angle": "LeftElbowAngle",
            "right_elbow_angle": "RightElbowAngle",
        }[key]

    def _provider_id(self):
        for key, button in self.provider_buttons.items():
            if button.isChecked():
                return key
        return "makehuman-hm08"

    def _provider_changed(self, provider_id):
        self._dirty = True
        self._refresh_provider_source()
        self._update_shape_enabled()
        self._refresh_status(
            "Avatar provider change is staged. Apply & Rebuild to swap the body source."
        )

    def _use_selected_provider_source(self):
        if self.avatar is None:
            return
        selection = [obj for obj in self.Gui.Selection.getSelection() if obj is not self.avatar]
        if not selection:
            self._refresh_status(
                "Select a FreeCAD body or mesh first, then use it as the provider source."
            )
            return
        self.provider_buttons["freecad-geometry"].setChecked(True)
        self._provider_source_object = selection[0]
        self._dirty = True
        self._refresh_provider_source()
        self._refresh_status(
            "Provider source staged: {}. Apply & Rebuild to use it.".format(
                getattr(selection[0], "Label", selection[0].Name)
            )
        )

    def _refresh_provider_source(self):
        if self.avatar is None:
            self.provider_source_label.setText("Source: none")
            return
        source = getattr(self, "_provider_source_object", None) or getattr(
            self.avatar, "ProviderSource", None
        )
        if source is None:
            text = "Source: none"
        else:
            text = "Source: {}".format(
                getattr(source, "Label", getattr(source, "Name", "FreeCAD object"))
            )
        self.provider_source_label.setText(text)
        self.provider_source.setEnabled(self._provider_id() == "freecad-geometry")

    def _preset_changed(self, preset):
        if self._loading:
            return
        from freecad_cloth.avatar.AvatarModel import Pose

        defaults = Pose(str(preset))
        for name in ("left_arm_angle", "right_arm_angle"):
            box = self._pose_boxes[name]
            box.blockSignals(True)
            box.setValue(float(getattr(defaults, name)))
            box.blockSignals(False)
        self._staged_changed()

    def _update_shape_labels(self):
        """Keep slider readouts explicit, including the neutral gender midpoint."""
        value = int(self.gender_slider.value())
        if value == 50:
            label = "Neutral"
        elif value < 50:
            label = "Feminine {}%".format(100 - value * 2)
        else:
            label = "Masculine {}%".format((value - 50) * 2)
        self.gender_value.setText(label)
        self.breast_value.setText("{}%".format(int(self.breast_slider.value())))

    def _shape_changed(self, _value=None):
        self._update_shape_labels()
        self._staged_changed()

    def _update_shape_enabled(self):
        """Disable MakeHuman-only controls for geometry-only provider surfaces."""
        is_human = self._provider_id() == "makehuman-hm08"
        self.shape_group.setEnabled(is_human)
        self.dimension_gizmo_toggle.setEnabled(is_human)
        if not is_human and self._dimension_controller is not None:
            self._dimension_controller.deactivate()
        elif is_human and self.dimension_gizmo_toggle.isChecked():
            self._toggle_dimension_gizmo(True)

    def _toggle_dimension_gizmo(self, enabled):
        """Attach or remove transient dimension handles in the active viewport."""
        if not enabled or self.avatar is None or self._provider_id() != "makehuman-hm08":
            if self._dimension_controller is not None:
                self._dimension_controller.deactivate()
            return
        if self._dimension_controller is None:
            try:
                from freecad_cloth.avatar.AvatarShapeGui import AvatarDimensionController

                self._dimension_controller = AvatarDimensionController(self)
            except (ImportError, RuntimeError, TypeError, ValueError):
                self.status.setText(
                    "3D dimensions are unavailable in this FreeCAD build; use the numeric measurements."
                )
                return
        if not self._dimension_controller.activate():
            self.status.setText(
                "3D dimensions are unavailable in this FreeCAD build; use the numeric measurements."
            )

    def _staged_changed(self):
        self._dirty = True
        self._refresh_status(
            "Unsaved mannequin edits are staged. Apply & Rebuild to update the body."
        )
        if self._dimension_controller is not None:
            self._dimension_controller.refresh()

    def _staged_parameters(self):
        from freecad_cloth.avatar.AvatarModel import AvatarParameters, Pose

        values = {key: box.value() for key, box in self._boxes.items()}
        pose = Pose(
            str(self.pose.currentText()),
            *(
                self._pose_boxes[key].value()
                for key in (
                    "left_arm_angle",
                    "right_arm_angle",
                    "left_elbow_angle",
                    "right_elbow_angle",
                )
            ),
        )
        return AvatarParameters(
            values,
            self.skin_offset.value(),
            Pose(
                pose.preset,
                pose.left_arm_angle,
                pose.right_arm_angle,
                pose.left_elbow_angle,
                pose.right_elbow_angle,
                tuple(self._staged_joint_rotations.values()),
            ),
            3,
            self.gender_slider.value() / 100.0,
            self.breast_slider.value() / 100.0,
        )

    def _apply(self):
        if self.avatar is None:
            return False
        params = self._staged_parameters()
        provider_id = self._provider_id()
        provider_source = getattr(self, "_provider_source_object", None) or getattr(
            self.avatar, "ProviderSource", None
        )
        if provider_id == "freecad-geometry" and (
            provider_source is None or provider_source is self.avatar
        ):
            self._refresh_status(
                "A FreeCAD body or mesh must be selected before switching to the FreeCAD geometry provider."
            )
            return False
        try:
            from freecad_cloth.avatar.AvatarCommands import apply_avatar_parameters

            apply_avatar_parameters(
                self.avatar,
                params,
                provider_id=provider_id,
                provider_source=provider_source if provider_id == "freecad-geometry" else None,
            )
        except (RuntimeError, TypeError, ValueError, OSError) as exc:
            self._dirty = True
            self._refresh_status(
                f"Mannequin rebuild failed; staged edits remain uncommitted: {exc}"
            )
            return False
        self._dirty = False
        self._update_arrangement_points()
        self._update_landmarks()
        self._refresh_provider_source()
        self._refresh_status("Mannequin rebuilt from applied persistent parameters.")
        self._update_shape_enabled()
        if self._dimension_controller is not None:
            self._dimension_controller.refresh()
        self._fit_view()
        return True

    def _load_skeleton_pose(self):
        from freecad_cloth.avatar.SkeletonPose import joint_rotation_map, joint_rotations_from_json

        rotations = joint_rotations_from_json(getattr(self.avatar, "JointPoseJSON", ""))
        self._staged_joint_rotations = joint_rotation_map(rotations)
        self._load_selected_joint()

    def _load_selected_joint(self, _index=0):
        bone = str(self.skeleton_joint.currentData())
        rotation = self._staged_joint_rotations.get(bone)
        values = (
            (0.0, 0.0, 0.0)
            if rotation is None
            else (
                float(rotation.x),
                float(rotation.y),
                float(rotation.z),
            )
        )
        for box, value in zip(
            (self.skeleton_x, self.skeleton_y, self.skeleton_z), values, strict=False
        ):
            box.blockSignals(True)
            box.setValue(value)
            box.blockSignals(False)

    def _joint_changed(self):
        from freecad_cloth.avatar.SkeletonPose import JointRotation

        bone = str(self.skeleton_joint.currentData())
        rotation = JointRotation(
            bone, self.skeleton_x.value(), self.skeleton_y.value(), self.skeleton_z.value()
        ).validate()
        values = dict(self._staged_joint_rotations)
        values[bone] = rotation
        if self.skeleton_symmetry.isChecked():
            mirrored = rotation.mirrored()
            if mirrored.bone != rotation.bone:
                values[mirrored.bone] = mirrored
        self._staged_joint_rotations = values
        self._staged_changed()

    def _symmetry_changed(self, checked):
        if not checked:
            return
        bone = str(self.skeleton_joint.currentData())
        rotation = self._staged_joint_rotations.get(bone)
        if rotation is None:
            return
        mirrored = rotation.mirrored()
        if mirrored.bone == rotation.bone:
            return
        self._staged_joint_rotations = {
            **self._staged_joint_rotations,
            mirrored.bone: mirrored,
        }
        self._staged_changed()

    def _reset_skeleton_pose(self):
        self._staged_joint_rotations = {}
        self._load_selected_joint()
        self._staged_changed()

    def _rebuild_geometry(self):
        from freecad_cloth.avatar.AvatarCommands import rebuild_avatar

        rebuild_avatar()

    def _update_arrangement_points(self):
        self.arrangement_points.clear()
        if self.avatar is None:
            return
        records = getattr(self.avatar, "ArrangementPoints", []) or []
        for item in records:
            try:
                name, coords = str(item).split("|", 1)
            except ValueError:
                continue
            self.arrangement_points.addItem(
                "{}: ({})".format(name.replace("_", " ").title(), coords)
            )

    def _update_landmarks(self):
        if self.avatar is None or not self.show_measurements.isChecked():
            self.landmarks.setText("")
            return
        entries = []
        for item in getattr(self.avatar, "Landmarks", []) or []:
            try:
                name, coords = str(item).split("|", 1)
            except ValueError:
                continue
            entries.append("{}: ({})".format(name.replace("_", " ").title(), coords))
        self.landmarks.setText("<b>Landmarks</b><br>" + "<br>".join(entries))

    def _landmarks_visibility_changed(self, _checked):
        self._update_landmarks()

    def _refresh_status(self, message=None):
        if self.avatar is None:
            self.status.setText(message or "No mannequin selected.")
            return
        suffix = " | staged changes" if self._dirty else ""
        self.status.setText(
            message
            or "Avatar status: {} | provider: {} | pose: {}{}".format(
                str(getattr(self.avatar, "AvatarStatus", "Unknown")),
                str(getattr(self.avatar, "AvatarProviderId", "makehuman-hm08")),
                str(getattr(self.avatar, "PosePreset", "standing")),
                suffix,
            )
        )

    def _fit_view(self):
        if self.Gui.activeDocument():
            self.Gui.activeDocument().activeView().fitAll()

    def accept(self):
        return self._apply()

    def reject(self):
        if self._dimension_controller is not None:
            self._dimension_controller.deactivate()
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
