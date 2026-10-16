# Copyright (C) 2026 FreeCAD Cloth contributors
"""FreeCAD task-panel frontend for the parametric Cloth mannequin.

Anthropometric edits are staged in the UI and applied atomically through the
existing AvatarCommands rebuild path. AvatarParameters remains authoritative
for validation and AvatarService remains the solver-neutral downstream API.
"""

import contextlib
from typing import ClassVar, Protocol


class _WidgetLayout(Protocol):
    """Minimal layout contract needed by the dynamically loaded PySide UI."""

    def addWidget(self, widget: object) -> None: ...


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

    PROPERTY_MAP: ClassVar[dict[str, str]] = {
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
        "stomach": "Stomach",
        "sleeve_length": "Sleeve_Length",
        "crotch_length": "Crotch_Length",
        "front_rise": "Front_Rise",
        "back_rise": "Back_Rise",
        "shirt_length": "Shirt_Length",
        "back_neck_to_waist": "Back_Neck_To_Waist",
    }
    SHAPE_PROPERTY_MAP: ClassVar[dict[str, str]] = {
        "gender": "GenderBlend",
        "breast_size": "BreastSize",
    }
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
        ("stomach", "Stomach circumference"),
        ("sleeve_length", "Sleeve length"),
    )
    FIT_TARGETS: ClassVar[frozenset[str]] = frozenset(
        {
            "height",
            "neck",
            "shoulder",
            "chest",
            "underbust",
            "waist",
            "hip",
            "upper_arm",
            "thigh",
            "knee",
            "calf",
            "inseam",
            "sleeve_length",
        }
    )
    PROPORTIONS = (
        ("inseam", "Inseam"),
        ("torso", "Torso length"),
        ("front_waist", "Front waist length"),
        ("back_waist", "Back waist length"),
        ("crotch_length", "Crotch length"),
        ("front_rise", "Front rise"),
        ("back_rise", "Back rise"),
        ("shirt_length", "Shirt length"),
        ("back_neck_to_waist", "Back neck to waist"),
    )
    POSE_FIELDS = (
        ("left_arm_angle", "Left arm"),
        ("right_arm_angle", "Right arm"),
        ("left_elbow_angle", "Left elbow bend"),
        ("right_elbow_angle", "Right elbow bend"),
    )
    PROVIDERS = (
        ("makehuman-hm08", "Anny parametric body (MakeHuman-compatible rig)"),
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
        title.setProperty("clothRole", "title")
        title_row.addWidget(title)
        title_row.addStretch(1)
        root.addLayout(title_row)

        # Keep the long title and viewport actions on separate rows so the task
        # pane's minimum width is controlled by the editor, not by its heading.
        action_row = QtWidgets.QHBoxLayout()
        self.dimension_gizmo_toggle = QtWidgets.QToolButton()
        self.dimension_gizmo_toggle.setText("3D Dimensions")
        self.dimension_gizmo_toggle.setCheckable(True)
        self.dimension_gizmo_toggle.setChecked(True)
        self.dimension_gizmo_toggle.setToolTip(
            "Show transient viewport handles for height, shoulder breadth, chest, waist and hip. "
            "Drag a handle to stage a dimension; Apply & Rebuild commits it."
        )
        action_row.addWidget(self.dimension_gizmo_toggle)
        self.pose_mode_button = QtWidgets.QPushButton("3D Pose Mode…")
        self.pose_mode_button.setToolTip(
            "Open the focused mannequin posing editor. Use the 3D rotation gizmo instead of typing joint angles."
        )
        action_row.addWidget(self.pose_mode_button)
        action_row.addStretch(1)
        root.addLayout(action_row)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        content = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content)
        self._boxes = {}
        self._pose_boxes = {}
        self._measurement_groups = []
        self._advanced_controls_built = False
        self._advanced_phenotype_overrides = {}
        self._advanced_local_change_overrides = {}
        self._advanced_phenotype_defaults = {}
        self._advanced_rows = []
        self._advanced_groups = []
        self._add_shape_group(content_layout)
        self._add_mass_target_group(content_layout)
        self._add_measurement_group(content_layout, "Body measurements", self.BODY)
        self._add_measurement_group(content_layout, "Proportions", self.PROPORTIONS)
        self._add_advanced_group(content_layout)

        provider = QtWidgets.QGroupBox("Avatar provider")
        provider_layout = QtWidgets.QVBoxLayout(provider)
        self._provider_ids = [key for key, _label in self.PROVIDERS]
        self.provider_group = QtWidgets.QButtonGroup(self.form)
        self.provider_group.setExclusive(True)
        self.provider_buttons = {}
        provider_row = QtWidgets.QHBoxLayout()
        for key, label in self.PROVIDERS:
            button = QtWidgets.QToolButton()
            button.setText("Anny body model" if key == "makehuman-hm08" else "FreeCAD geometry")
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
        self.rebuild_button = self.apply_button  # Compatibility alias; do not duplicate the action.
        self.fit_button = QtWidgets.QPushButton("Fit view")
        from freecad_cloth.common.UiDesign import mark_button

        mark_button(self.apply_button, "primary")
        mark_button(self.fit_button, "secondary")
        controls.addWidget(self.apply_button)
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
        self.fit_button.clicked.connect(self._fit_view)
        self.pose_mode_button.clicked.connect(self._open_pose_mode)
        self.gender_slider.valueChanged.connect(self._shape_changed)
        self.breast_slider.valueChanged.connect(self._shape_changed)
        self.dimension_gizmo_toggle.toggled.connect(self._toggle_dimension_gizmo)
        self.mass_target_enabled.toggled.connect(self._mass_target_toggled)
        self.mass_target.valueChanged.connect(self._staged_changed)
        self.advanced_toggle.toggled.connect(self._toggle_advanced_parameters)
        self.advanced_search.textChanged.connect(self._filter_advanced_parameters)
        self.reset_advanced_button.clicked.connect(self._reset_advanced_parameters)
        self._dimension_controller = None
        self._update_shape_enabled()

        from freecad_cloth.common.UiDesign import apply_panel_style

        apply_panel_style(self.form)

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
            if key in self.FIT_TARGETS:
                tooltip = (
                    "Target in millimetres. The Anny/clad-body fitting objective constrains "
                    "this dimension when the mannequin is rebuilt."
                )
            else:
                tooltip = (
                    "Stored in millimetres for garment reference and derived landmarks. "
                    "This value is not an independent constraint in the current body-surface fit."
                )
            box.setToolTip(tooltip)
            layout.addRow(label, box)
            self._boxes[key] = box
        parent.addWidget(group)
        self._measurement_groups.append(group)

    def _add_mass_target_group(self, parent: _WidgetLayout) -> None:
        """Expose clad-body's differentiable body-mass target without mixing units."""
        _, _, QtWidgets = _modules()
        group = QtWidgets.QGroupBox("Body composition")
        layout = QtWidgets.QFormLayout(group)
        self.mass_target_enabled = QtWidgets.QCheckBox("Fit target body mass")
        self.mass_target_enabled.setToolTip(
            "Optionally constrain clad-body's differentiable mass_kg measurement. "
            "When enabled, the fit adjusts Anny's global weight phenotype."
        )
        layout.addRow(self.mass_target_enabled)
        self.mass_target = QtWidgets.QDoubleSpinBox()
        self.mass_target.setRange(25.0, 250.0)
        self.mass_target.setDecimals(1)
        self.mass_target.setSingleStep(0.5)
        self.mass_target.setSuffix(" kg")
        self.mass_target.setValue(70.0)
        self.mass_target.setKeyboardTracking(False)
        self.mass_target.setEnabled(False)
        self.mass_target.setToolTip(
            "Target body mass in kilograms. Disabled by default so the body shape is "
            "controlled by the main measurement targets and Anny phenotypes."
        )
        layout.addRow("Target mass", self.mass_target)
        parent.addWidget(group)
        self.mass_group = group

    def _mass_target_toggled(self, enabled: bool) -> None:
        self.mass_target.setEnabled(bool(enabled))
        self._staged_changed()

    def _add_advanced_group(self, parent: _WidgetLayout) -> None:
        """Add lazy-loaded, searchable Anny controls without cluttering the common editor."""
        _, _, QtWidgets = _modules()
        try:
            from PySide import QtCore
        except ImportError:
            from PySide2 import QtCore

        self.advanced_toggle = QtWidgets.QToolButton()
        self.advanced_toggle.setText("Advanced Anny parameters")
        self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.setChecked(False)
        self.advanced_toggle.setArrowType(QtCore.Qt.RightArrow)
        self.advanced_toggle.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.advanced_toggle.setToolTip(
            "Reveal every normalized Anny phenotype and every paired local-morph target in the installed model. "
            "These overrides are applied after anthropometric fitting and may change resulting measurements."
        )
        parent.addWidget(self.advanced_toggle)

        self.advanced_content = QtWidgets.QWidget()
        advanced_layout = QtWidgets.QVBoxLayout(self.advanced_content)
        advanced_layout.setContentsMargins(4, 4, 4, 4)
        self.advanced_content.setVisible(False)

        help_text = QtWidgets.QLabel(
            "Advanced values override the fitted shape. Phenotypes use range 0 to 1; body morphs use -1 to 1. "
            "Primary Gender blend and Breast fullness remain in Body shape."
        )
        help_text.setWordWrap(True)
        advanced_layout.addWidget(help_text)

        search_row = QtWidgets.QHBoxLayout()
        self.advanced_search = QtWidgets.QLineEdit()
        self.advanced_search.setPlaceholderText("Filter by parameter name…")
        self.advanced_search.setClearButtonEnabled(True)
        self.reset_advanced_button = QtWidgets.QPushButton("Reset advanced")
        self.reset_advanced_button.setToolTip(
            "Clear all advanced overrides and restore Anny defaults."
        )
        search_row.addWidget(self.advanced_search, 1)
        search_row.addWidget(self.reset_advanced_button)
        advanced_layout.addLayout(search_row)

        self.advanced_tabs = QtWidgets.QTabWidget()
        self._advanced_pages = {}
        for page_key, page_title in (("phenotypes", "Phenotypes"), ("morphs", "Body morphs")):
            scroll = QtWidgets.QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setMinimumHeight(230)
            contents = QtWidgets.QWidget()
            page_layout = QtWidgets.QVBoxLayout(contents)
            page_layout.setContentsMargins(4, 4, 4, 4)
            page_layout.setSpacing(6)
            scroll.setWidget(contents)
            self.advanced_tabs.addTab(scroll, page_title)
            self._advanced_pages[page_key] = {
                "scroll": scroll,
                "contents": contents,
                "layout": page_layout,
                "groups": {},
            }
        advanced_layout.addWidget(self.advanced_tabs)
        parent.addWidget(self.advanced_content)

    def _advanced_category(self, name: str, kind: str) -> str:
        """Group raw model labels into scannable families while preserving search terms."""
        if kind == "phenotype":
            labels = {
                "age": "Age",
                "gender": "Gender",
                "muscle": "Muscle",
                "weight": "Weight",
                "height": "Height",
                "proportions": "Proportions",
                "cupsize": "Cup size",
                "firmness": "Firmness",
                "african": "Race blend",
                "asian": "Race blend",
                "caucasian": "Race blend",
            }
            return labels.get(name, "Other phenotypes")
        if name.startswith("measure-"):
            return "Anthropometric morphs"
        if name.startswith("breast-"):
            return "Breast shape"
        if name.startswith("stomach-") or name.startswith("belly-"):
            return "Abdomen shape"
        if name.startswith(("arm-", "hand-", "shoulder-")):
            return "Arms and shoulders"
        if name.startswith(("leg-", "thigh-", "knee-", "calf-", "foot-")):
            return "Legs and feet"
        if name.startswith(("torso-", "waist-", "hip-", "chest-", "neck-")):
            return "Torso"
        if name.startswith(("head-", "face-", "nose-", "eye-", "mouth-", "ear-")):
            return "Head and face"
        return "Other body morphs"

    @staticmethod
    def _display_parameter_name(name: str) -> str:
        """Turn model labels into a readable label without losing their exact API name."""
        return str(name).replace("_", " ").replace("-", " ").strip().title()

    def _append_advanced_control(
        self,
        kind: str,
        name: str,
        default: float,
        value: float,
        page_key: str,
        low: float,
        high: float,
    ) -> None:
        _, _, QtWidgets = _modules()
        page = self._advanced_pages[page_key]
        category = self._advanced_category(name, kind)
        if category not in page["groups"]:
            group = QtWidgets.QGroupBox(category)
            group_layout = QtWidgets.QVBoxLayout(group)
            group_layout.setContentsMargins(6, 6, 6, 6)
            group_layout.setSpacing(3)
            page["layout"].addWidget(group)
            page["groups"][category] = {"widget": group, "layout": group_layout, "rows": []}
            self._advanced_groups.append(group)
        group_data = page["groups"][category]

        row = QtWidgets.QWidget()
        row_layout = QtWidgets.QHBoxLayout(row)
        row_layout.setContentsMargins(2, 1, 2, 1)
        label = QtWidgets.QLabel(self._display_parameter_name(name))
        label.setMinimumWidth(100)
        label.setMaximumWidth(170)
        label.setWordWrap(True)
        box = QtWidgets.QDoubleSpinBox()
        box.setDecimals(3)
        box.setSingleStep(0.01)
        box.setRange(float(low), float(high))
        box.setValue(float(value))
        box.setKeyboardTracking(False)
        box.setToolTip(
            f"Anny parameter: {name}\nDefault: {default:.3f}\n"
            + (
                "Normalized phenotype, range 0 to 1. Applied after measurement fitting."
                if kind == "phenotype"
                else "Local body morph, range -1 to 1. Applied after measurement fitting."
            )
        )
        label.setToolTip(name)
        row_layout.addWidget(label, 1)
        row_layout.addWidget(box)
        group_data["layout"].addWidget(row)
        group_data["rows"].append(row)
        row.setProperty(
            "clothSearchText", f"{name} {self._display_parameter_name(name)}".casefold()
        )
        self._advanced_rows.append(
            {
                "name": name,
                "kind": kind,
                "page": page_key,
                "row": row,
                "group": group_data["widget"],
                "box": box,
                "default": float(default),
            }
        )
        box.valueChanged.connect(
            lambda current, control_kind=kind, parameter_name=name: (
                self._advanced_parameter_changed(control_kind, parameter_name, current)
            )
        )

    def _toggle_advanced_parameters(self, expanded: bool) -> None:
        """Populate the long-tail parameter editor only when the user opens it."""
        self.advanced_content.setVisible(bool(expanded))
        try:
            from PySide import QtCore
        except ImportError:
            from PySide2 import QtCore
        self.advanced_toggle.setArrowType(QtCore.Qt.DownArrow if expanded else QtCore.Qt.RightArrow)
        if expanded and not self._advanced_controls_built:
            try:
                from freecad_cloth.avatar.AnnyAvatarBackend import (
                    available_anny_local_change_labels,
                    available_anny_phenotype_labels,
                    default_anny_phenotype_values,
                )

                self._advanced_phenotype_defaults = default_anny_phenotype_values(
                    gender=self.gender_slider.value() / 100.0,
                    breast_size=self.breast_slider.value() / 100.0,
                )
                for name in available_anny_phenotype_labels():
                    # These have dedicated primary controls in Body shape.
                    if name in {"gender", "cupsize"}:
                        continue
                    default = float(self._advanced_phenotype_defaults[name])
                    value = float(self._advanced_phenotype_overrides.get(name, default))
                    self._append_advanced_control(
                        "phenotype",
                        name,
                        default,
                        value,
                        "phenotypes",
                        0.0,
                        1.0,
                    )
                for name in available_anny_local_change_labels():
                    # Breast fullness has a dedicated primary slider and cannot
                    # be independently overridden by a local morph value.
                    if name == "breast-volume-vert-up":
                        continue
                    default = 0.0
                    value = float(self._advanced_local_change_overrides.get(name, default))
                    self._append_advanced_control(
                        "morph", name, default, value, "morphs", -1.0, 1.0
                    )
                for page in self._advanced_pages.values():
                    page["layout"].addStretch(1)
                self._advanced_controls_built = True
                self._filter_advanced_parameters(self.advanced_search.text())
            except (ImportError, OSError, RuntimeError, TypeError, ValueError) as exc:
                self.status.setText(
                    "Advanced Anny parameters could not be loaded. "
                    f"The standard measurement controls remain available: {exc}"
                )
                self.advanced_content.setVisible(False)
                self.advanced_toggle.setChecked(False)
                return
        elif expanded:
            self._filter_advanced_parameters(self.advanced_search.text())

    def _filter_advanced_parameters(self, text: str) -> None:
        """Filter parameter rows live across both advanced tabs."""
        query = str(text).strip().casefold()
        visible_by_group = {}
        visible_by_page = dict.fromkeys(self._advanced_pages, False)
        for item in self._advanced_rows:
            matches = not query or query in str(item["row"].property("clothSearchText"))
            item["row"].setVisible(matches)
            visible_by_group[item["group"]] = visible_by_group.get(item["group"], False) or matches
            visible_by_page[item["page"]] = visible_by_page[item["page"]] or matches
        for group in self._advanced_groups:
            group.setVisible(visible_by_group.get(group, False))
        if query and not visible_by_page.get(
            "phenotypes" if self.advanced_tabs.currentIndex() == 0 else "morphs", False
        ):
            target_page = next(
                (index for index, key in enumerate(self._advanced_pages) if visible_by_page[key]),
                None,
            )
            if target_page is not None:
                self.advanced_tabs.setCurrentIndex(target_page)

    def _advanced_parameter_changed(self, kind: str, name: str, value: float) -> None:
        """Persist only non-default overrides while keeping defaults discoverable in the UI."""
        default = self._advanced_phenotype_defaults.get(name, 0.5) if kind == "phenotype" else 0.0
        overrides = (
            self._advanced_phenotype_overrides
            if kind == "phenotype"
            else self._advanced_local_change_overrides
        )
        if abs(float(value) - float(default)) <= 0.0005:
            overrides.pop(name, None)
        else:
            overrides[name] = float(value)
        self._staged_changed()

    def _reset_advanced_parameters(self) -> None:
        """Clear every advanced parameter override in one staged operation."""
        self._advanced_phenotype_overrides.clear()
        self._advanced_local_change_overrides.clear()
        for item in self._advanced_rows:
            box = item["box"]
            box.blockSignals(True)
            box.setValue(float(item["default"]))
            box.blockSignals(False)
        self._staged_changed()

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
        self.gender_value.setMinimumWidth(64)
        self.gender_value.setAlignment(QtCore.Qt.AlignRight)
        gender_wrapper = QtWidgets.QWidget()
        gender_layout = QtWidgets.QVBoxLayout(gender_wrapper)
        gender_layout.setContentsMargins(0, 0, 0, 0)
        gender_layout.setSpacing(2)
        gender_layout.addWidget(gender_container)
        gender_layout.addWidget(self.gender_value, 0, QtCore.Qt.AlignRight)
        layout.addRow("Gender blend", gender_wrapper)

        breast_row = QtWidgets.QHBoxLayout()
        breast_row.addWidget(QtWidgets.QLabel("Less"))
        self.breast_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.breast_slider.setRange(0, 100)
        self.breast_slider.setSingleStep(1)
        self.breast_slider.setPageStep(10)
        self.breast_slider.setToolTip(
            "Stage additional breast projection from the neutral base shape (0-100%)."
        )
        breast_row.addWidget(self.breast_slider, 1)
        breast_row.addWidget(QtWidgets.QLabel("More"))
        breast_container = QtWidgets.QWidget()
        breast_container.setLayout(breast_row)
        self.breast_value = QtWidgets.QLabel("0%")
        self.breast_value.setMinimumWidth(64)
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
        from freecad_cloth.avatar.AvatarModel import AvatarParameters

        payload = str(getattr(self.avatar, "ParametersJSON", "") or "")
        mass_target = None
        if payload:
            try:
                stored_parameters = AvatarParameters.from_json(payload)
                mass_target = stored_parameters.mass_target_kg
                self._advanced_phenotype_overrides = dict(stored_parameters.phenotype_overrides)
                self._advanced_local_change_overrides = dict(
                    stored_parameters.local_change_overrides
                )
            except (TypeError, ValueError):
                self._advanced_phenotype_overrides = {}
                self._advanced_local_change_overrides = {}
        for key, box in self._boxes.items():
            box.blockSignals(True)
            box.setValue(float(getattr(self.avatar, self.PROPERTY_MAP[key])))
            box.blockSignals(False)
        self.gender_slider.blockSignals(True)
        self.gender_slider.setValue(round(100.0 * float(getattr(self.avatar, "GenderBlend", 0.5))))
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
        self.mass_target_enabled.blockSignals(True)
        self.mass_target_enabled.setChecked(mass_target is not None)
        self.mass_target_enabled.blockSignals(False)
        self.mass_target.blockSignals(True)
        self.mass_target.setValue(70.0 if mass_target is None else float(mass_target))
        self.mass_target.blockSignals(False)
        self.mass_target.setEnabled(mass_target is not None)
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
        self._update_shape_enabled()
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
            label = f"Feminine {100 - value * 2}%"
        else:
            label = f"Masculine {(value - 50) * 2}%"
        self.gender_value.setText(label)
        self.breast_value.setText(f"{int(self.breast_slider.value())}%")

    def _shape_changed(self, _value=None):
        self._update_shape_labels()
        self._staged_changed()

    def _update_shape_enabled(self):
        """Disable MakeHuman-only controls for geometry-only provider surfaces."""
        is_human = self._provider_id() == "makehuman-hm08"
        self.shape_group.setEnabled(is_human)
        for group in self._measurement_groups:
            group.setEnabled(is_human)
        self.skin_offset.setEnabled(is_human)
        self.show_measurements.setEnabled(is_human)
        self.dimension_gizmo_toggle.setEnabled(is_human)
        self.mass_group.setEnabled(is_human)
        self.advanced_toggle.setEnabled(is_human)
        self.advanced_content.setEnabled(is_human)
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
            4,
            self.gender_slider.value() / 100.0,
            self.breast_slider.value() / 100.0,
            dict(self._advanced_phenotype_overrides),
            dict(self._advanced_local_change_overrides),
            self.mass_target.value() if self.mass_target_enabled.isChecked() else None,
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
        from freecad_cloth.common.UiDesign import set_status

        if self.avatar is None:
            set_status(self.status, message or "No mannequin selected.", state="warning")
            return
        suffix = " | staged changes" if self._dirty else ""
        set_status(
            self.status,
            message
            or "Avatar status: {} | provider: {} | pose: {}{}".format(
                str(getattr(self.avatar, "AvatarStatus", "Unknown")),
                str(getattr(self.avatar, "AvatarProviderId", "makehuman-hm08")),
                str(getattr(self.avatar, "PosePreset", "standing")),
                suffix,
            ),
            state="warning" if self._dirty else "info",
        )

    def _fit_view(self):
        """Fit the viewport on explicit user request, not every rebuild."""
        if self.Gui.activeDocument():
            self.Gui.activeDocument().activeView().fitAll()

    def accept(self):
        success = self._apply()
        if success and self._dimension_controller is not None:
            self._dimension_controller.deactivate()
        return success

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
