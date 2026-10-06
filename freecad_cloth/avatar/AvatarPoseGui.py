"""Focused 3D posing UI for the merged Cloth mannequin skeleton.

PoseMode is intentionally separate from the anthropometric avatar editor. The
task panel keeps common posing actions visible while the viewport carries the
primary manipulation. Exact Euler entry is retained behind a precision drawer.
"""


def _modules():
    import FreeCAD as App
    import FreeCADGui as Gui

    try:
        from PySide import QtCore, QtWidgets
    except ImportError:
        from PySide2 import QtCore, QtWidgets
    return App, Gui, QtCore, QtWidgets


def joint_world_positions(parameters):
    """Return posed world positions for the controllable authored joints."""
    from freecad_cloth.avatar.HierarchicalPose import _manual_pose_rotations
    from freecad_cloth.avatar.HumanoidMesh import (
        _joint_point,
        _load_source_vertices,
        _make_source_fitted_mapper,
        load_makehuman_skeleton,
    )
    from freecad_cloth.avatar.SkeletonPose import CONTROLLABLE_JOINTS, build_bone_transforms

    source_vertices = _load_source_vertices()
    skeleton = load_makehuman_skeleton()
    mapper = _make_source_fitted_mapper(
        source_vertices, parameters, float(parameters.skin_offset)
    )
    rotations = _manual_pose_rotations(parameters)
    transforms = build_bone_transforms(
        source_vertices,
        skeleton,
        mapper,
        rotations,
    )
    result = {}
    for bone, label in CONTROLLABLE_JOINTS:
        data = skeleton["bones"].get(bone)
        if data is None:
            continue
        fitted_head = mapper(_joint_point(source_vertices, skeleton["joints"][data["head"]]))
        result[bone] = tuple(
            float(value) for value in transforms[bone].apply(fitted_head)
        )
    return result


class SkeletonPoseController:
    """Viewport overlay and Coin3D trackball controller for mannequin joints."""

    GIZMO_SIZE = 75.0
    JOINT_PICK_RADIUS = 28.0

    def __init__(self, panel):
        self.panel = panel
        self.App = panel.App
        self.Gui = panel.Gui
        self.view = None
        self.scene_graph = None
        self.overlay = None
        self.gizmo_separator = None
        self.gizmo_transform = None
        self.gizmo = None
        self.mouse_callback = None
        self.selected_bone = None
        self.base_rotation = None
        self._positions = {}

    def _coin(self):
        from pivy import coin

        return coin

    def _screen_position(self, point):
        projected = self.view.getPointOnScreen(self.App.Vector(*point))
        size = self.view.getSize()
        return float(projected[0]), float(size[1] - projected[1])

    def _build_positions(self):
        self._positions = joint_world_positions(self.panel._staged_parameters())

    def activate(self):
        """Enable X-ray joints and the selected-joint trackball."""
        if self.view is not None:
            return
        if self.panel.avatar is None:
            raise RuntimeError("create a Cloth Human Mannequin first")
        if str(getattr(self.panel.avatar, "AvatarProviderId", "makehuman-hm08")) != "makehuman-hm08":
            self.panel.status.setText(
                "Pose Mode is available for the MakeHuman HM08 avatar provider."
            )
            return

        self.view = self.Gui.activeDocument().activeView()
        self.scene_graph = self.view.getSceneGraph()
        coin = self._coin()

        self.overlay = coin.SoSeparator()
        self.overlay.setName("ClothAvatarPoseOverlay")
        self.scene_graph.addChild(self.overlay)

        self._add_skeleton_overlay(coin)
        try:
            self.mouse_callback = self.view.addEventCallbackPivy(
                coin.SoMouseButtonEvent.getClassTypeId(),
                self._mouse_event,
            )
        except Exception as exc:
            if "No SWIG wrapped library loaded" not in str(exc):
                raise
            self.mouse_callback = None
            self.panel.status.setText(
                "Pose Mode: viewport joint picking is unavailable in this FreeCAD/SWIG build; "
                "use the joint selector and rotation gizmo."
            )
        self._build_positions()
        bone = str(self.panel.skeleton_joint.currentData())
        if bone:
            self.select_joint(bone)
        self.panel.status.setText(
            "Pose Mode: click a joint, then drag the rotation rings. Symmetry and 5° snapping are on."
        )

    def deactivate(self):
        """Remove transient viewport nodes and callbacks."""
        if self.view is None:
            return
        coin = self._coin()
        try:
            if self.mouse_callback is not None:
                self.view.removeEventCallbackPivy(
                    coin.SoMouseButtonEvent.getClassTypeId(),
                    self.mouse_callback,
                )
        except (AttributeError, RuntimeError):
            pass
        try:
            if self.gizmo_separator is not None:
                self.scene_graph.removeChild(self.gizmo_separator)
            if self.overlay is not None:
                self.scene_graph.removeChild(self.overlay)
        except (AttributeError, RuntimeError):
            pass
        self.mouse_callback = None
        self.gizmo = None
        self.gizmo_transform = None
        self.gizmo_separator = None
        self.overlay = None
        self.scene_graph = None
        self.view = None

    def _add_skeleton_overlay(self, coin):
        draw = coin.SoDrawStyle()
        draw.lineWidth = 2.0
        point_draw = coin.SoDrawStyle()
        point_draw.pointSize = 8.0
        joint_color = coin.SoBaseColor()
        joint_color.rgb = (0.82, 0.82, 0.82)
        bone_color = coin.SoBaseColor()
        bone_color.rgb = (0.65, 0.65, 0.65)

        self._build_positions()
        from freecad_cloth.avatar.SkeletonPose import CONTROLLABLE_JOINTS

        point_list = [
            self._positions[bone]
            for bone, _label in CONTROLLABLE_JOINTS
            if bone in self._positions
        ]
        if point_list:
            points_sep = coin.SoSeparator()
            points = coin.SoCoordinate3()
            points.point.setValues(0, len(point_list), [tuple(position) for position in point_list])
            point_set = coin.SoPointSet()
            point_set.numPoints = len(point_list)
            points_sep.addChild(point_draw)
            points_sep.addChild(joint_color)
            points_sep.addChild(points)
            points_sep.addChild(point_set)
            self.overlay.addChild(points_sep)

        skeleton = self._joint_connections()
        if skeleton:
            coordinates = []
            counts = []
            for head, tail in skeleton:
                coordinates.extend((head, tail))
                counts.append(2)
            bones_sep = coin.SoSeparator()
            coord = coin.SoCoordinate3()
            coord.point.setValues(0, len(coordinates), coordinates)
            line_set = coin.SoLineSet()
            line_set.numVertices.setValues(0, len(counts), counts)
            bones_sep.addChild(draw)
            bones_sep.addChild(bone_color)
            bones_sep.addChild(coord)
            bones_sep.addChild(line_set)
            self.overlay.addChild(bones_sep)

    def _joint_connections(self):
        from freecad_cloth.avatar.HumanoidMesh import load_makehuman_skeleton
        from freecad_cloth.avatar.SkeletonPose import CONTROLLABLE_JOINTS

        skeleton = load_makehuman_skeleton()
        connections = []
        for bone, _label in CONTROLLABLE_JOINTS:
            data = skeleton["bones"].get(bone)
            if data is None:
                continue
            for candidate in CONTROLLABLE_JOINTS:
                if candidate[0] not in self._positions:
                    continue
                child_data = skeleton["bones"].get(candidate[0])
                if child_data and child_data.get("parent") == bone:
                    connections.append(
                        (self._positions[bone], self._positions[candidate[0]])
                    )
                    break
        return tuple(connections)

    def _remove_overlay_children(self):
        if self.overlay is None:
            return
        while self.overlay.getNumChildren():
            self.overlay.removeChild(0)

    def refresh_overlay(self, keep_gizmo=False):
        if self.overlay is None or self.view is None:
            return
        self._remove_overlay_children()
        self._add_skeleton_overlay(self._coin())
        if self.selected_bone and not keep_gizmo:
            self._create_gizmo(self.selected_bone)

    def _create_gizmo(self, bone):
        coin = self._coin()
        try:
            if self.gizmo_separator is not None:
                self.scene_graph.removeChild(self.gizmo_separator)
        except (AttributeError, RuntimeError):
            pass
        self.gizmo_separator = coin.SoSeparator()
        self.gizmo_transform = coin.SoTransform()
        self.gizmo = coin.SoTrackballDragger()
        self.gizmo.scaleFactor.setValue(
            self.GIZMO_SIZE,
            self.GIZMO_SIZE,
            self.GIZMO_SIZE,
        )
        self.gizmo.setAnimationEnabled(False)
        self.gizmo_separator.addChild(self.gizmo_transform)
        self.gizmo_separator.addChild(self.gizmo)
        point = self._positions.get(bone)
        if point is not None:
            self.gizmo_transform.translation.setValue(coin.SbVec3f(*point))
        self.scene_graph.addChild(self.gizmo_separator)
        self.gizmo.addStartCallback(self._gizmo_start)
        self.gizmo.addMotionCallback(self._gizmo_motion)
        self.gizmo.addFinishCallback(self._gizmo_finish)

    def select_joint(self, bone):
        bone = str(bone)
        if bone not in self._positions:
            return
        self.selected_bone = bone
        self.panel._select_joint_without_preview(bone)
        self._create_gizmo(bone)

    def _gizmo_start(self, _data, dragger):
        from freecad_cloth.avatar.SkeletonPose import JointRotation

        self.base_rotation = self.panel._staged_joint_rotations.get(
            self.selected_bone,
            JointRotation(self.selected_bone),
        )
        dragger.rotation.setValue(
            self._coin().SbVec3f(0.0, 0.0, 1.0),
            0.0,
        )
        self.panel.status.setText(
            "Rotating {} — release to keep the staged pose; Cancel restores it.".format(
                self.panel._joint_label(self.selected_bone)
            )
        )

    def _dragger_quaternion(self, dragger):
        rotation = dragger.rotation.getValue()
        values = rotation.getValue()
        return tuple(float(values[index]) for index in range(4))

    def _gizmo_motion(self, _data, dragger):
        if self.selected_bone is None or self.base_rotation is None:
            return
        try:
            quaternion = self._dragger_quaternion(dragger)
            delta = self.App.Rotation(*quaternion)
            base = self.App.Rotation()
            base.setEulerAngles(
                self.App.Rotation.Extrinsic_XYZ,
                float(self.base_rotation.x),
                float(self.base_rotation.y),
                float(self.base_rotation.z),
            )
            combined = delta.multiply(base)
            angles = combined.getEulerAngles(self.App.Rotation.Extrinsic_XYZ)
            x, y, z = (float(value) for value in angles)
            self.panel._stage_joint_rotation(
                self.selected_bone,
                x,
                y,
                z,
                preview=True,
            )
        except (AttributeError, IndexError, RuntimeError, TypeError, ValueError):
            return

    def _gizmo_finish(self, _data, _dragger):
        self.base_rotation = None
        if self.selected_bone:
            self.panel.status.setText(
                "{} posed. Click Apply & Rebuild to keep the change.".format(
                    self.panel._joint_label(self.selected_bone)
                )
            )
            self.refresh_overlay()

    def _mouse_event(self, event_callback):
        coin = self._coin()
        event = event_callback.getEvent()
        if event.getState() != coin.SoMouseButtonEvent.DOWN:
            return
        if event.getButton() != coin.SoMouseButtonEvent.BUTTON1:
            return
        if self.gizmo is not None and self.gizmo.isActive:
            return
        position = event.getPosition()
        size = self.view.getSize()
        screen = (float(position[0]), float(size[1] - position[1]))
        try:
            positions = {
                bone: self._screen_position(point)
                for bone, point in self._positions.items()
            }
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return
        best = None
        best_distance = self.JOINT_PICK_RADIUS
        for bone, point in positions.items():
            distance = ((point[0] - screen[0]) ** 2 + (point[1] - screen[1]) ** 2) ** 0.5
            if distance < best_distance:
                best = bone
                best_distance = distance
        if best is not None:
            self.select_joint(best)


class AvatarPoseTaskPanel:
    """Compact pose editor designed around direct 3D manipulation."""

    PRESETS = (("standing", "Standing"), ("sewing", "Sewing"), ("sitting", "Sitting"))

    def __init__(self, avatar=None):
        App, Gui, QtCore, QtWidgets = _modules()
        self.App, self.Gui, self.QtCore, self.QtWidgets = App, Gui, QtCore, QtWidgets
        self.avatar = avatar or self._find_avatar()
        self.form = QtWidgets.QWidget()
        self.form.setObjectName("ClothAvatarPoseTaskPanel")
        root = QtWidgets.QVBoxLayout(self.form)

        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Pose Mode")
        title.setStyleSheet("font-weight: bold; font-size: 15px;")
        header.addWidget(title)
        header.addStretch(1)
        self.symmetry = QtWidgets.QCheckBox("Symmetry")
        self.symmetry.setChecked(True)
        self.symmetry.setToolTip("Mirror left/right joint rotations around the mannequin center line.")
        header.addWidget(self.symmetry)
        self.angle_snap = QtWidgets.QCheckBox("Snap 5°")
        self.angle_snap.setChecked(True)
        self.angle_snap.setToolTip("Round dragged rotations to 5 degree increments.")
        header.addWidget(self.angle_snap)
        root.addLayout(header)

        preset_row = QtWidgets.QHBoxLayout()
        preset_label = QtWidgets.QLabel("Preset")
        preset_row.addWidget(preset_label)
        self.preset_group = QtWidgets.QButtonGroup(self.form)
        self.preset_group.setExclusive(True)
        self.preset_buttons = {}
        for preset, label in self.PRESETS:
            button = QtWidgets.QToolButton()
            button.setText(label)
            button.setCheckable(True)
            button.setAutoRaise(True)
            self.preset_group.addButton(button)
            self.preset_buttons[preset] = button
            preset_row.addWidget(button)
            button.clicked.connect(lambda checked=False, value=preset: self._select_preset(value))
        preset_row.addStretch(1)
        root.addLayout(preset_row)

        main = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        joint_panel = QtWidgets.QWidget()
        joint_layout = QtWidgets.QVBoxLayout(joint_panel)
        joint_title = QtWidgets.QLabel("Joints")
        joint_title.setStyleSheet("font-weight: bold;")
        joint_layout.addWidget(joint_title)
        self.joints = QtWidgets.QTreeWidget()
        self.joints.setHeaderHidden(True)
        self.joints.setRootIsDecorated(True)
        self.joints.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self._populate_joints()
        joint_layout.addWidget(self.joints, 1)
        main.addWidget(joint_panel)

        selected = QtWidgets.QGroupBox("Selected joint")
        selected_layout = QtWidgets.QVBoxLayout(selected)
        self.selected_label = QtWidgets.QLabel("Select a joint in the list or 3D view.")
        self.selected_label.setStyleSheet("font-weight: bold;")
        selected_layout.addWidget(self.selected_label)

        instruction = QtWidgets.QLabel(
            "Drag a colored ring to rotate around one axis, or drag the trackball for free rotation. Release to stage the pose."
        )
        instruction.setWordWrap(True)
        selected_layout.addWidget(instruction)

        self._sliders = {}
        self._angle_labels = {}
        for axis, text in (("x", "X"), ("y", "Y"), ("z", "Z")):
            row = QtWidgets.QHBoxLayout()
            label = QtWidgets.QLabel(text)
            label.setFixedWidth(18)
            slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            slider.setRange(-180, 180)
            slider.setSingleStep(1)
            slider.setPageStep(15)
            slider.setTracking(True)
            value = QtWidgets.QLabel("0°")
            value.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            value.setFixedWidth(42)
            row.addWidget(label)
            row.addWidget(slider, 1)
            row.addWidget(value)
            selected_layout.addLayout(row)
            self._sliders[axis] = slider
            self._angle_labels[axis] = value
            slider.valueChanged.connect(
                lambda value, axis=axis: self._slider_changed(axis, value)
            )

        self.precision = QtWidgets.QToolButton()
        self.precision.setText("Precision")
        self.precision.setCheckable(True)
        self.precision.setChecked(False)
        self.precision.setArrowType(QtCore.Qt.RightArrow)
        self.precision.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
        selected_layout.addWidget(self.precision)
        self.precision_fields = {}
        precision_widget = QtWidgets.QWidget()
        precision_layout = QtWidgets.QFormLayout(precision_widget)
        for axis in ("x", "y", "z"):
            box = QtWidgets.QDoubleSpinBox()
            box.setRange(-180.0, 180.0)
            box.setDecimals(1)
            box.setSuffix("°")
            precision_layout.addRow("{} rotation".format(axis.upper()), box)
            self.precision_fields[axis] = box
            box.valueChanged.connect(
                lambda value, axis=axis: self._precision_changed(axis, value)
            )
        selected_layout.addWidget(precision_widget)
        self.precision_widget = precision_widget
        self.precision_widget.setVisible(False)
        self.precision.toggled.connect(self._toggle_precision)
        main.addWidget(selected)
        main.setSizes([340, 270])
        root.addWidget(main, 1)

        action_row = QtWidgets.QHBoxLayout()
        self.reset_button = QtWidgets.QPushButton("Reset pose")
        self.fit_button = QtWidgets.QPushButton("Fit view")
        action_row.addWidget(self.reset_button)
        action_row.addWidget(self.fit_button)
        action_row.addStretch(1)
        root.addLayout(action_row)

        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        footer = QtWidgets.QHBoxLayout()
        footer.addStretch(1)
        self.apply_button = QtWidgets.QPushButton("Apply & Rebuild")
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        footer.addWidget(self.apply_button)
        footer.addWidget(self.cancel_button)
        root.addLayout(footer)

        self._staged_joint_rotations = {}
        self._staged_pose_preset = "standing"
        self._loading = True
        self._load()
        self._loading = False

        self.joints.currentItemChanged.connect(self._joint_item_changed)
        self.reset_button.clicked.connect(self._reset_pose)
        self.fit_button.clicked.connect(self._fit_view)
        self.apply_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

        self.controller = SkeletonPoseController(self)
        self.controller.activate()

    def _find_avatar(self):
        doc = self.App.ActiveDocument
        if doc is None:
            return None
        return next(
            (o for o in doc.Objects if getattr(o, "AvatarType", "") == "ClothAvatar"),
            None,
        )

    def _populate_joints(self):
        from freecad_cloth.avatar.SkeletonPose import CONTROLLABLE_JOINTS

        groups = {
            "Torso": [],
            "Left arm": [],
            "Right arm": [],
            "Left leg": [],
            "Right leg": [],
        }
        for bone, label in CONTROLLABLE_JOINTS:
            if bone.endswith(".L") and "leg" not in bone and any(
                token in bone for token in ("clavicle", "arm", "wrist")
            ):
                groups["Left arm"].append((bone, label))
            elif bone.endswith(".R") and "leg" not in bone and any(
                token in bone for token in ("clavicle", "arm", "wrist")
            ):
                groups["Right arm"].append((bone, label))
            elif bone.endswith(".L") and any(
                token in bone for token in ("upperleg", "lowerleg", "foot")
            ):
                groups["Left leg"].append((bone, label))
            elif bone.endswith(".R") and any(
                token in bone for token in ("upperleg", "lowerleg", "foot")
            ):
                groups["Right leg"].append((bone, label))
            else:
                groups["Torso"].append((bone, label))

        for group_name, items in groups.items():
            top = self.QtWidgets.QTreeWidgetItem([group_name])
            top.setFlags(top.flags() & ~self.QtCore.Qt.ItemIsSelectable)
            self.joints.addTopLevelItem(top)
            for bone, label in items:
                child = self.QtWidgets.QTreeWidgetItem([label])
                child.setData(0, self.QtCore.Qt.UserRole, bone)
                top.addChild(child)
            top.setExpanded(True)

    def _load(self):
        if self.avatar is None:
            self.status.setText("Create a Cloth Human Mannequin first.")
            self.apply_button.setEnabled(False)
            return
        from freecad_cloth.avatar.SkeletonPose import (
            joint_rotation_map,
            joint_rotations_from_json,
        )

        self._staged_joint_rotations = joint_rotation_map(
            joint_rotations_from_json(getattr(self.avatar, "JointPoseJSON", ""))
        )
        current_preset = str(getattr(self.avatar, "PosePreset", "standing"))
        self._staged_pose_preset = current_preset
        button = self.preset_buttons.get(current_preset, self.preset_buttons["standing"])
        button.setChecked(True)
        self._select_first_joint()

    def _select_first_joint(self):
        for index in range(self.joints.topLevelItemCount()):
            top = self.joints.topLevelItem(index)
            if top.childCount():
                self.joints.setCurrentItem(top.child(0))
                return

    def _joint_item_changed(self, current, _previous):
        if current is None:
            return
        bone = current.data(0, self.QtCore.Qt.UserRole)
        if bone:
            self._select_joint_without_preview(str(bone))
            self.controller.select_joint(str(bone))

    def _select_joint_without_preview(self, bone):
        self.skeleton_joint_index = str(bone)
        label = self._joint_label(str(bone))
        self.selected_label.setText(label)
        rotation = self._staged_joint_rotations.get(str(bone))
        values = (0.0, 0.0, 0.0) if rotation is None else (
            float(rotation.x),
            float(rotation.y),
            float(rotation.z),
        )
        for axis, value in zip(("x", "y", "z"), values, strict=False):
            self._set_axis_value(axis, value)

    @staticmethod
    def _joint_label(bone):
        from freecad_cloth.avatar.SkeletonPose import JOINT_LABELS

        return JOINT_LABELS.get(str(bone), str(bone))

    def _set_axis_value(self, axis, value):
        value = float(value)
        slider = self._sliders[axis]
        label = self._angle_labels[axis]
        precision = self.precision_fields[axis]
        slider.blockSignals(True)
        slider.setValue(max(-180, min(180, int(round(value)))))
        slider.blockSignals(False)
        label.setText("{:.0f}°".format(value))
        precision.blockSignals(True)
        precision.setValue(value)
        precision.blockSignals(False)

    def _slider_changed(self, axis, value):
        if self._loading or not getattr(self, "skeleton_joint_index", None):
            return
        values = {key: self._sliders[key].value() for key in ("x", "y", "z")}
        self._stage_joint_rotation(
            self.skeleton_joint_index,
            values["x"],
            values["y"],
            values["z"],
            preview=True,
        )

    def _precision_changed(self, axis, value):
        if self._loading or not getattr(self, "skeleton_joint_index", None):
            return
        values = {}
        for key in ("x", "y", "z"):
            values[key] = (
                float(value) if key == axis else float(self.precision_fields[key].value())
            )
        self._stage_joint_rotation(
            self.skeleton_joint_index,
            values["x"],
            values["y"],
            values["z"],
            preview=True,
        )

    def _stage_joint_rotation(self, bone, x, y, z, preview=False):
        from freecad_cloth.avatar.SkeletonPose import JointRotation

        values = dict(self._staged_joint_rotations)
        rotation = JointRotation(str(bone), float(x), float(y), float(z)).validate()
        if self.angle_snap.isChecked():
            rotation = JointRotation(
                rotation.bone,
                round(rotation.x / 5.0) * 5.0,
                round(rotation.y / 5.0) * 5.0,
                round(rotation.z / 5.0) * 5.0,
            )
        values[rotation.bone] = rotation
        if self.symmetry.isChecked():
            mirrored_bone = rotation.mirrored().bone
            if mirrored_bone != rotation.bone:
                values[mirrored_bone] = JointRotation(
                    mirrored_bone, rotation.x, rotation.y, rotation.z
                )
        self._staged_joint_rotations = values
        self._select_joint_without_preview(str(bone))
        if preview:
            self._preview_rebuild()
        self.status.setText(
            "{} staged at X {:.0f}° Y {:.0f}° Z {:.0f}°.".format(
                self._joint_label(bone),
                rotation.x,
                rotation.y,
                rotation.z,
            )
        )

    def _staged_parameters(self):
        from freecad_cloth.avatar.AvatarModel import AvatarParameters, Pose

        measurements = {
            key: float(getattr(self.avatar, property_name))
            for key, property_name in self._measurement_map().items()
        }
        current_pose = Pose(
            str(getattr(self, "_staged_pose_preset", getattr(self.avatar, "PosePreset", "standing"))),
            float(getattr(self.avatar, "LeftArmAngle", 12.0)),
            float(getattr(self.avatar, "RightArmAngle", 12.0)),
            float(getattr(self.avatar, "LeftElbowAngle", 0.0)),
            float(getattr(self.avatar, "RightElbowAngle", 0.0)),
            tuple(self._staged_joint_rotations.values()),
        )
        return AvatarParameters(
            measurements,
            float(getattr(self.avatar, "SkinOffset", 0.0)),
            current_pose,
        )

    @staticmethod
    def _measurement_map():
        return {
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

    def _select_preset(self, preset):
        if self._loading:
            return
        self._staged_joint_rotations = {}
        self._staged_pose_preset = str(preset)
        self._preview_rebuild()
        self._select_first_joint()
        self.status.setText(
            "{} preset staged. Manual joint edits will start from this baseline.".format(
                preset.title()
            )
        )

    def _preview_rebuild(self):
        if self.avatar is None:
            return
        from freecad_cloth.avatar.AvatarCommands import _mesh_data
        from freecad_cloth.avatar.AvatarModel import generate_mesh

        try:
            params = self._staged_parameters()
            if hasattr(self, "_staged_pose_preset"):
                from freecad_cloth.avatar.AvatarModel import AvatarParameters, Pose

                params = AvatarParameters(
                    params.measurements,
                    params.skin_offset,
                    Pose(
                        self._staged_pose_preset,
                        params.pose.left_arm_angle,
                        params.pose.right_arm_angle,
                        params.pose.left_elbow_angle,
                        params.pose.right_elbow_angle,
                        params.pose.joint_rotations,
                    ),
                )
            vertices, triangles, _landmarks = generate_mesh(params)
            self.avatar.Mesh = _mesh_data(vertices, triangles)
            self.avatar.Document.recompute()
            self.controller.refresh_overlay(keep_gizmo=bool(self.controller.gizmo is not None and self.controller.gizmo.isActive))
        except (AttributeError, RuntimeError, TypeError, ValueError):
            self.status.setText("Preview unavailable; the staged values remain editable.")

    def _reset_pose(self):
        self._staged_joint_rotations = {}
        self._staged_pose_preset = str(getattr(self.avatar, "PosePreset", "standing"))
        self._preview_rebuild()
        self._select_first_joint()
        self.status.setText("Pose reset to the selected preset baseline.")

    def _toggle_precision(self, expanded):
        self.precision.setArrowType(
            self.QtCore.Qt.DownArrow if expanded else self.QtCore.Qt.RightArrow
        )
        self.precision_widget.setVisible(bool(expanded))

    def _fit_view(self):
        if self.Gui.activeDocument():
            self.Gui.activeDocument().activeView().fitAll()

    def accept(self):
        if self.avatar is None:
            return False
        from freecad_cloth.avatar.AvatarCommands import rebuild_avatar
        from freecad_cloth.avatar.SkeletonPose import joint_rotations_to_json

        self.avatar.JointPoseJSON = joint_rotations_to_json(
            tuple(self._staged_joint_rotations.values())
        )
        if hasattr(self, "_staged_pose_preset"):
            self.avatar.PosePreset = self._staged_pose_preset
        rebuild_avatar()
        self.controller.deactivate()
        return True

    def reject(self):
        try:
            from freecad_cloth.avatar.AvatarCommands import rebuild_avatar

            rebuild_avatar()
        finally:
            self.controller.deactivate()
        return True

    def getStandardButtons(self):
        _, _, _, QtWidgets = _modules()
        return QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel


def show_avatar_pose_task(avatar=None):
    """Open the focused Pose Mode task panel."""
    _App, Gui, _QtCore, _QtWidgets = _modules()
    panel = AvatarPoseTaskPanel(avatar)
    Gui.Control.showDialog(panel)
    return panel
