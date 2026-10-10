"""Focused 3D posing UI for the merged Cloth mannequin skeleton.

PoseMode is intentionally separate from the anthropometric avatar editor. The
task panel keeps only essential posing aids visible while the viewport carries
the primary manipulation. Exact Euler entry is retained behind a precision drawer.
"""

import contextlib
import math

from freecad_cloth.shared.viewport_gizmo_style import (
    ACTIVE_COLOR,
    JOINT_COLOR,
    POSE_AXIS_COLORS,
    RIG_ACTIVE_JOINT_POINT_SIZE,
    RIG_ACTIVE_LINE_WIDTH,
    RIG_EDITABLE_COLOR,
    RIG_EDITABLE_LINE_WIDTH,
    RIG_JOINT_POINT_SIZE,
    RIG_PASSIVE_COLOR,
    RIG_PASSIVE_LINE_WIDTH,
    ROTATION_ARC_ANGLE_DEGREES,
    ROTATION_ARROW_HEIGHT,
    ROTATION_ARROW_RADIUS,
    ROTATION_GIZMO_SCALE,
    ROTATION_PIVOT_RADIUS,
    ROTATION_RING_RADIUS,
    ROTATION_RING_THICKNESS,
)


def _modules():
    import FreeCAD as App
    import FreeCADGui as Gui

    try:
        from PySide import QtCore, QtWidgets
    except ImportError:
        from PySide2 import QtCore, QtWidgets
    return App, Gui, QtCore, QtWidgets


def _pose_world_state(parameters):
    """Return the exact rig transforms used to deform the visible mannequin."""
    from freecad_cloth.avatar.HierarchicalPose import pose_world_state

    return pose_world_state(parameters)


def joint_world_positions(parameters):
    """Return posed world positions for the controllable authored joints."""
    from freecad_cloth.avatar.HumanoidMesh import _joint_point
    from freecad_cloth.avatar.SkeletonPose import CONTROLLABLE_JOINTS

    source_vertices, skeleton, mapper, transforms = _pose_world_state(parameters)
    result = {}
    for bone, _label in CONTROLLABLE_JOINTS:
        data = skeleton["bones"].get(bone)
        if data is None or bone not in transforms:
            continue
        fitted_head = mapper(_joint_point(source_vertices, skeleton["joints"][data["head"]]))
        result[bone] = tuple(float(value) for value in transforms[bone].apply(fitted_head))
    return result


def skeleton_world_segments(parameters):
    """Return posed head/tail segments for the complete authored skeleton."""
    from freecad_cloth.avatar.HumanoidMesh import _joint_point

    source_vertices, skeleton, mapper, transforms = _pose_world_state(parameters)
    segments = {}
    joints = {}
    for bone, data in skeleton["bones"].items():
        transform = transforms.get(bone)
        if transform is None:
            continue
        fitted_head = mapper(_joint_point(source_vertices, skeleton["joints"][data["head"]]))
        fitted_tail = mapper(_joint_point(source_vertices, skeleton["joints"][data["tail"]]))
        head = tuple(float(value) for value in transform.apply(fitted_head))
        tail = tuple(float(value) for value in transform.apply(fitted_tail))
        segments[bone] = (head, tail)
        joints.setdefault(data["head"], head)
        joints[data["tail"]] = tail
    return segments, joints


class _FallbackGizmo:
    """Panel-only pose fallback used when Coin/SWIG viewport controls are unavailable."""

    is_fallback = True
    is_visual = False
    isActive = False

    def __init__(self, objects=()):
        self.objects = tuple(objects)


class _NativeGizmoHandle:
    """Compatibility wrapper exposing the legacy controller gizmo surface."""

    is_fallback = False
    is_visual = True

    def __init__(self, dragger, controller):
        self.dragger = dragger
        self._controller = controller

    @property
    def isActive(self):
        return bool(self._controller._gizmo_dragging)


class SkeletonPoseController:
    """Viewport overlay and Coin3D rotation controller for mannequin joints."""

    GIZMO_SIZE = 75.0
    BONE_PICK_RADIUS = 12.0
    JOINT_PICK_RADIUS = 20.0

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
        self._location_callback = None
        self._hover_separator = None
        self._hover_bone = None
        self.selected_bone = None
        self.base_rotation = None
        self._positions = {}
        self._skeleton_segments = {}
        self._gizmo_dragging = False
        self.gizmo_mode = None
        self.gizmo_style = None
        self.gizmo_style_error = None
        self._native_dragger = None
        self._active_gizmo_axis = None
        self.fallback_gizmo_object = None
        self.viewport_runtime_error = None

    def _coin(self):
        from pivy import coin

        return coin

    def _screen_position(self, point):
        projected = self.view.getPointOnScreen(self.App.Vector(*point))
        size = self.view.getSize()
        return float(projected[0]), float(size[1] - projected[1])

    @staticmethod
    def _screen_segment_distance(point, start, end):
        """Return the 2D distance from a point to a projected bone segment."""
        px, py = point
        ax, ay = start
        bx, by = end
        dx = bx - ax
        dy = by - ay
        length_sq = dx * dx + dy * dy
        if length_sq <= 1e-9:
            return ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
        t = ((px - ax) * dx + (py - ay) * dy) / length_sq
        t = max(0.0, min(1.0, t))
        closest_x = ax + t * dx
        closest_y = ay + t * dy
        return ((px - closest_x) ** 2 + (py - closest_y) ** 2) ** 0.5

    def _build_positions(self):
        self._positions = joint_world_positions(self.panel._staged_parameters())

    def _build_skeleton(self):
        from freecad_cloth.avatar.SkeletonPose import CONTROLLABLE_JOINTS

        self._skeleton_segments, joints = skeleton_world_segments(self.panel._staged_parameters())
        self._positions = {
            bone: self._skeleton_segments[bone][0]
            for bone, _label in CONTROLLABLE_JOINTS
            if bone in self._skeleton_segments
        }
        return joints

    def _native_transform_type(self, coin):
        type_id = coin.SoType.fromName("SoTransformDragger")
        if type_id.isBad():
            return None
        return type_id

    def activate(self):
        """Enable the X-ray skeleton and selected-joint rotation gizmo."""
        if self.view is not None:
            return
        if self.panel.avatar is None:
            raise RuntimeError("create a Cloth Human Mannequin first")
        if (
            str(getattr(self.panel.avatar, "AvatarProviderId", "makehuman-hm08"))
            != "makehuman-hm08"
        ):
            self.panel.status.setText(
                "Pose Mode is available for the MakeHuman HM08 avatar provider."
            )
            return

        self.view = self.Gui.activeDocument().activeView()
        try:
            # Import Pivy before requesting FreeCAD's Coin proxy. FreeCAD's
            # embedded SWIG dispatcher discovers the registered Pivy runtime
            # through the module initialized by this import.
            coin = self._coin()
            self.scene_graph = self.view.getSceneGraph()
        except Exception as exc:
            if "No SWIG wrapped library loaded" not in str(exc):
                raise
            self.viewport_runtime_error = repr(exc)
            self.scene_graph = None
            self.overlay = None
            self._build_positions()
            self.gizmo_mode = "fallback-panel"
            self.gizmo = _FallbackGizmo()
            self.panel._select_first_joint()
            self.panel.joint_list_toggle.setChecked(True)
            self.panel.angle_snap.setEnabled(False)
            self.panel.angle_snap.setToolTip(
                "Unavailable without viewport rotation; Exact angles is the precise fallback."
            )
            self.panel.instruction_label.setText(
                "Viewport posing is unavailable. Use Joint list to select a joint, "
                "then Exact angles to edit rotation."
            )
            bone = str(getattr(self.panel, "skeleton_joint_index", ""))
            if bone:
                self.select_joint(bone)
            self.panel.status.setText(
                "Pose Mode: viewport posing is unavailable in this FreeCAD build; "
                "use Joint list and Exact angles."
            )
            return

        self.overlay = coin.SoSeparator()
        self.overlay.setName("ClothAvatarPoseOverlay")
        # Pose controls are an interaction overlay: keep them visible even when
        # the mannequin surface would otherwise win the depth test.
        depth = coin.SoDepthBuffer()
        depth.test = False
        depth.write = False
        self.overlay.addChild(depth)
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
                "Pose Mode: bone clicking is unavailable in this FreeCAD/SWIG build; "
                "use Joint list to select a joint, then Exact angles to edit rotation."
            )
        try:
            self._location_callback = self.view.addEventCallbackPivy(
                coin.SoLocation2Event.getClassTypeId(),
                self._location_event,
            )
        except Exception as exc:
            if "No SWIG wrapped library loaded" not in str(exc):
                raise
            self._location_callback = None
        self._build_positions()
        bone = str(getattr(self.panel, "skeleton_joint_index", "") or "")
        if not bone:
            self.panel._select_first_joint()
            bone = str(getattr(self.panel, "skeleton_joint_index", "") or "")
        if bone:
            self.select_joint(bone)
        self.panel.status.setText("Click a bone to select · drag a rotation ring to pose.")

    def _clear_fallback_gizmo(self):
        obj = self.fallback_gizmo_object
        self.fallback_gizmo_object = None
        if obj is None:
            return
        try:
            doc = self.panel.avatar.Document
            if obj.Name in [item.Name for item in doc.Objects]:
                doc.removeObject(obj.Name)
                doc.recompute()
        except (AttributeError, RuntimeError):
            pass

    def _create_fallback_gizmo(self, bone):
        # Do not draw a fake manipulator when viewport dragging is unavailable.
        # The joint list and exact-angle drawer are the honest fallback controls.
        self._clear_fallback_gizmo()
        self.fallback_gizmo_object = None
        self.gizmo = _FallbackGizmo()

    def deactivate(self):
        """Remove transient viewport nodes and callbacks."""
        if self.view is None:
            return
        if self.scene_graph is None:
            self.mouse_callback = None
            self._location_callback = None
            self._clear_hover_overlay()
            self._clear_fallback_gizmo()
            self.gizmo = None
            self.gizmo_transform = None
            self.gizmo_separator = None
            self.overlay = None
            self.scene_graph = None
            self._native_dragger = None
            self._gizmo_dragging = False
            self.gizmo_mode = None
            self._skeleton_segments = {}
            self.view = None
            return
        coin = self._coin()
        try:
            if self.mouse_callback is not None:
                self.view.removeEventCallbackPivy(
                    coin.SoMouseButtonEvent.getClassTypeId(),
                    self.mouse_callback,
                )
            if self._location_callback is not None:
                self.view.removeEventCallbackPivy(
                    coin.SoLocation2Event.getClassTypeId(),
                    self._location_callback,
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
        self._location_callback = None
        self._clear_hover_overlay()
        self.gizmo = None
        self.gizmo_transform = None
        self.gizmo_separator = None
        self.overlay = None
        self.scene_graph = None
        self._native_dragger = None
        self._gizmo_dragging = False
        self.gizmo_mode = None
        self.gizmo_style = None
        self.gizmo_style_error = None
        self._skeleton_segments = {}
        self.view = None

    def _add_skeleton_overlay(self, coin):
        """Draw the complete posed skeleton with selectable controls highlighted."""
        from freecad_cloth.avatar.SkeletonPose import CONTROLLABLE_BONES

        joints = self._build_skeleton()
        editable = set(CONTROLLABLE_BONES)

        def add_lines(parent, segments, width, rgb):
            if not segments:
                return
            coordinates = []
            counts = []
            for head, tail in segments:
                coordinates.extend((head, tail))
                counts.append(2)
            separator = coin.SoSeparator()
            draw = coin.SoDrawStyle()
            draw.lineWidth = float(width)
            color = coin.SoBaseColor()
            color.rgb = rgb
            coord = coin.SoCoordinate3()
            coord.point.setValues(0, len(coordinates), coordinates)
            line_set = coin.SoLineSet()
            line_set.numVertices.setValues(0, len(counts), counts)
            separator.addChild(draw)
            separator.addChild(color)
            separator.addChild(coord)
            separator.addChild(line_set)
            parent.addChild(separator)

        passive_segments = [
            segment
            for bone, segment in self._skeleton_segments.items()
            if bone not in editable and bone != self.selected_bone
        ]
        editable_segments = [
            segment
            for bone, segment in self._skeleton_segments.items()
            if bone in editable and bone != self.selected_bone
        ]
        selected_segments = (
            [self._skeleton_segments[self.selected_bone]]
            if self.selected_bone in self._skeleton_segments
            else []
        )

        # Blender-style posing convention: the full rig remains visible, while
        # editable/active bones are visually stronger than structural bones.
        add_lines(self.overlay, passive_segments, RIG_PASSIVE_LINE_WIDTH, RIG_PASSIVE_COLOR)
        add_lines(self.overlay, editable_segments, RIG_EDITABLE_LINE_WIDTH, RIG_EDITABLE_COLOR)
        add_lines(self.overlay, selected_segments, RIG_ACTIVE_LINE_WIDTH, ACTIVE_COLOR)

        point_list = list(joints.values())
        if point_list:
            point_draw = coin.SoDrawStyle()
            point_draw.pointSize = RIG_JOINT_POINT_SIZE
            joint_color = coin.SoBaseColor()
            joint_color.rgb = JOINT_COLOR
            points = coin.SoCoordinate3()
            points.point.setValues(0, len(point_list), point_list)
            point_set = coin.SoPointSet()
            point_set.numPoints = len(point_list)
            points_sep = coin.SoSeparator()
            points_sep.addChild(point_draw)
            points_sep.addChild(joint_color)
            points_sep.addChild(points)
            points_sep.addChild(point_set)
            self.overlay.addChild(points_sep)

        if self.selected_bone in self._positions:
            selected_draw = coin.SoDrawStyle()
            selected_draw.pointSize = RIG_ACTIVE_JOINT_POINT_SIZE
            selected_color = coin.SoBaseColor()
            selected_color.rgb = ACTIVE_COLOR
            selected_points = coin.SoCoordinate3()
            selected_points.point.setValues(
                0,
                1,
                [self._positions[self.selected_bone]],
            )
            selected_point_set = coin.SoPointSet()
            selected_point_set.numPoints = 1
            selected_sep = coin.SoSeparator()
            selected_sep.addChild(selected_draw)
            selected_sep.addChild(selected_color)
            selected_sep.addChild(selected_points)
            selected_sep.addChild(selected_point_set)
            self.overlay.addChild(selected_sep)

    def _joint_connections(self):
        return tuple(self._skeleton_segments.values())

    def _remove_overlay_children(self):
        if self.overlay is None:
            return
        while self.overlay.getNumChildren():
            self.overlay.removeChild(0)

    def refresh_overlay(self, keep_gizmo=False):
        if self.view is None:
            return
        if self.scene_graph is None:
            if self.selected_bone:
                self._build_positions()
                self._create_fallback_gizmo(self.selected_bone)
            return
        self._remove_overlay_children()
        self._add_skeleton_overlay(self._coin())
        if self.selected_bone and not keep_gizmo:
            self._create_gizmo(self.selected_bone)
        elif self.selected_bone and self.gizmo_transform is not None:
            point = self._positions.get(self.selected_bone)
            if point is not None:
                self.gizmo_transform.translation.setValue(self._coin().SbVec3f(*point))

    def _remove_gizmo(self):
        if self.scene_graph is not None and self.gizmo_separator is not None:
            with contextlib.suppress(AttributeError, RuntimeError):
                self.scene_graph.removeChild(self.gizmo_separator)
        self.gizmo_separator = None
        self.gizmo_transform = None
        self.gizmo = None
        self.gizmo_mode = None
        self.gizmo_style = None
        self.gizmo_style_error = None
        self._native_dragger = None
        self._gizmo_dragging = False

    def _configure_axis_rotation_dragger(self, coin, dragger, rgb, geometry_scale):
        """Configure one native FreeCAD rotation ring with cone tips and a pivot sphere."""
        rotator_type = coin.SoType.fromName("SoRotatorGeometry2")
        if rotator_type.isBad():
            self.gizmo_style_error = "SoRotatorGeometry2 is not registered"
            return False
        required = (
            "setPart",
            "geometryScale",
            "rotationIncrement",
            "rotation",
            "color",
            "activeColor",
            "baseGeomVisible",
        )
        if any(not hasattr(dragger, item) for item in required):
            self.gizmo_style_error = "SoRotationDragger proxy is missing its public API"
            return False

        rotator = rotator_type.createInstance()
        if rotator is None:
            self.gizmo_style_error = "failed to instantiate SoRotatorGeometry2"
            return False
        if not dragger.setPart("rotator", rotator):
            self.gizmo_style_error = "cannot replace SoRotationDragger rotator part"
            return False

        dragger.geometryScale.setValue(
            geometry_scale,
            geometry_scale,
            geometry_scale,
        )
        dragger.rotationIncrement.setValue(
            math.radians(5.0 if self.panel.angle_snap.isChecked() else 1.0)
        )
        dragger.rotation.setValue(
            coin.SbVec3f(0.0, 0.0, 1.0),
            0.0,
        )

        rotator.arcAngle.setValue(math.radians(ROTATION_ARC_ANGLE_DEGREES))
        rotator.arcRadius.setValue(ROTATION_RING_RADIUS)
        rotator.arcThickness.setValue(ROTATION_RING_THICKNESS)
        rotator.sphereRadius.setValue(ROTATION_PIVOT_RADIUS)
        rotator.coneBottomRadius.setValue(ROTATION_ARROW_RADIUS)
        rotator.coneHeight.setValue(ROTATION_ARROW_HEIGHT)
        rotator.leftArrowVisible.setValue(True)
        rotator.rightArrowVisible.setValue(True)

        dragger.color.setValue(*rgb)
        dragger.activeColor.setValue(*ACTIVE_COLOR)
        dragger.baseGeomVisible.setValue(False)
        return True

    def _create_native_gizmo(self, coin):
        # Use three direct axis draggers: this keeps the visual geometry and
        # interaction semantics independent of SoTransformDragger child-kit exposure.
        type_id = coin.SoType.fromName("SoRotationDragger")
        if type_id.isBad():
            return False

        self.gizmo_style_error = None
        axis_specs = (
            ("X", (1.0, 0.0, 0.0), POSE_AXIS_COLORS["X"]),
            ("Y", (0.0, 1.0, 0.0), POSE_AXIS_COLORS["Y"]),
            ("Z", (0.0, 0.0, 1.0), POSE_AXIS_COLORS["Z"]),
        )
        geometry_scale = ROTATION_GIZMO_SCALE

        try:
            local_z = coin.SbVec3f(0.0, 0.0, 1.0)
            draggers = []
            for axis_name, world_axis, rgb in axis_specs:
                dragger = type_id.createInstance()
                if dragger is None:
                    self.gizmo_style_error = "failed to instantiate SoRotationDragger"
                    return False
                required = (
                    "rotation",
                    "rotationIncrement",
                    "geometryScale",
                    "addStartCallback",
                    "addMotionCallback",
                    "addFinishCallback",
                    "setName",
                )
                if any(not hasattr(dragger, item) for item in required):
                    self.gizmo_style_error = (
                        "SoRotationDragger proxy is missing required fields or callbacks"
                    )
                    return False

                axis_transform = coin.SoTransform()
                axis_transform.rotation.setValue(
                    coin.SbRotation(
                        local_z,
                        coin.SbVec3f(*world_axis),
                    )
                )
                self.gizmo_separator.addChild(axis_transform)

                if not self._configure_axis_rotation_dragger(
                    coin,
                    dragger,
                    rgb,
                    geometry_scale,
                ):
                    return False

                dragger.setName("ClothPoseRotation" + axis_name)
                self.gizmo_separator.addChild(dragger)
                draggers.append(dragger)
                dragger.addStartCallback(self._gizmo_start)
                dragger.addMotionCallback(self._gizmo_motion)
                dragger.addFinishCallback(self._gizmo_finish)

            self.scene_graph.addChild(self.gizmo_separator)
            self._native_dragger = draggers
            self.gizmo = _NativeGizmoHandle(draggers[0], self)
            self.gizmo_mode = "native"
            self.gizmo_style = "axis-rings-cones"
            return True
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            self.gizmo_style = None
            self.gizmo_style_error = repr(exc)
            if self.gizmo_separator is not None:
                with contextlib.suppress(AttributeError, RuntimeError):
                    self.scene_graph.removeChild(self.gizmo_separator)
            return False

    def _create_trackball_gizmo(self, coin):
        self.gizmo = coin.SoTrackballDragger()
        self.gizmo.scaleFactor.setValue(
            self.GIZMO_SIZE,
            self.GIZMO_SIZE,
            self.GIZMO_SIZE,
        )
        self.gizmo.setAnimationEnabled(False)
        self.gizmo_separator.addChild(self.gizmo)
        self.scene_graph.addChild(self.gizmo_separator)
        self.gizmo_mode = "trackball-fallback"
        self._native_dragger = None
        self.gizmo.addStartCallback(self._gizmo_start)
        self.gizmo.addMotionCallback(self._gizmo_motion)
        self.gizmo.addFinishCallback(self._gizmo_finish)

    def _create_gizmo(self, bone):
        if self.scene_graph is None:
            self.gizmo_separator = None
            self.gizmo_transform = None
            self.gizmo_mode = "fallback-panel"
            self._create_fallback_gizmo(bone)
            return
        coin = self._coin()
        self._remove_gizmo()
        self.gizmo_separator = coin.SoSeparator()
        depth = coin.SoDepthBuffer()
        depth.test = False
        depth.write = False
        self.gizmo_separator.addChild(depth)
        self.gizmo_transform = coin.SoTransform()
        point = self._positions.get(bone)
        if point is not None:
            self.gizmo_transform.translation.setValue(coin.SbVec3f(*point))
        self.gizmo_separator.addChild(self.gizmo_transform)
        if self._create_native_gizmo(coin):
            return
        self._create_trackball_gizmo(coin)

    def select_joint(self, bone):
        bone = str(bone)
        if bone not in self._positions:
            return
        self.selected_bone = bone
        self._set_hover_bone(None)
        self.panel._select_joint_without_preview(bone)
        self._create_gizmo(bone)

    def _gizmo_start(self, _data, dragger):
        from freecad_cloth.avatar.SkeletonPose import JointRotation

        self._gizmo_dragging = True
        self.base_rotation = self.panel._staged_joint_rotations.get(
            self.selected_bone,
            JointRotation(self.selected_bone),
        )
        name = ""
        with contextlib.suppress(AttributeError, RuntimeError):
            name = str(dragger.getName().getString())
        self._active_gizmo_axis = {
            "ClothPoseRotationX": (1.0, 0.0, 0.0),
            "ClothPoseRotationY": (0.0, 1.0, 0.0),
            "ClothPoseRotationZ": (0.0, 0.0, 1.0),
        }.get(name)

        dragger.rotation.setValue(
            self._coin().SbVec3f(0.0, 0.0, 1.0),
            0.0,
        )
        if hasattr(dragger, "rotationIncrement"):
            dragger.rotationIncrement.setValue(
                math.radians(5.0 if self.panel.angle_snap.isChecked() else 1.0)
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
            angle = math.degrees(2.0 * math.atan2(float(quaternion[2]), float(quaternion[3])))
            if self._active_gizmo_axis is None:
                return
            delta = self.App.Rotation(
                self.App.Vector(*self._active_gizmo_axis),
                angle,
            )
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
        self._gizmo_dragging = False
        self.base_rotation = None
        self._active_gizmo_axis = None
        if self.selected_bone:
            self.panel.status.setText(
                "{} posed. Click Apply & Rebuild to keep the change.".format(
                    self.panel._joint_label(self.selected_bone)
                )
            )
            self.refresh_overlay()

    def _clear_hover_overlay(self):
        if self._hover_separator is None or self.scene_graph is None:
            self._hover_separator = None
            self._hover_bone = None
            return
        with contextlib.suppress(AttributeError, RuntimeError):
            self.scene_graph.removeChild(self._hover_separator)
        self._hover_separator = None
        self._hover_bone = None

    def _set_hover_bone(self, bone):
        bone = None if bone is None else str(bone)
        if bone == self._hover_bone:
            return
        self._clear_hover_overlay()
        if bone is None or bone == self.selected_bone or self.scene_graph is None:
            return
        segment = self._skeleton_segments.get(bone)
        if segment is None:
            return
        try:
            coin = self._coin()
            separator = coin.SoSeparator()
            depth = coin.SoDepthBuffer()
            depth.test = False
            depth.write = False
            draw = coin.SoDrawStyle()
            draw.lineWidth = 4.0
            color = coin.SoBaseColor()
            color.rgb = (0.95, 0.88, 0.38)
            coord = coin.SoCoordinate3()
            coord.point.setValues(0, 2, [segment[0], segment[1]])
            line_set = coin.SoLineSet()
            line_set.numVertices.setValue(2)
            separator.addChild(depth)
            separator.addChild(draw)
            separator.addChild(color)
            separator.addChild(coord)
            separator.addChild(line_set)
            self.scene_graph.addChild(separator)
            self._hover_separator = separator
            self._hover_bone = bone
        except (AttributeError, RuntimeError, TypeError, ValueError):
            self._hover_separator = None
            self._hover_bone = None

    def _pick_bone(self, screen, include_joint_fallback=False):
        from freecad_cloth.avatar.SkeletonPose import CONTROLLABLE_BONES

        try:
            projected_segments = {
                bone: (
                    self._screen_position(segment[0]),
                    self._screen_position(segment[1]),
                )
                for bone, segment in self._skeleton_segments.items()
            }
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return None

        best = None
        best_distance = self.BONE_PICK_RADIUS
        for bone in CONTROLLABLE_BONES:
            segment = projected_segments.get(bone)
            if segment is None:
                continue
            distance = self._screen_segment_distance(
                screen,
                segment[0],
                segment[1],
            )
            if distance < best_distance:
                best = bone
                best_distance = distance

        if best is None and include_joint_fallback:
            for bone, point in {
                name: self._screen_position(value) for name, value in self._positions.items()
            }.items():
                distance = ((point[0] - screen[0]) ** 2 + (point[1] - screen[1]) ** 2) ** 0.5
                if distance < best_distance:
                    best = bone
                    best_distance = distance
        return best

    def _location_event(self, event_callback):
        if self._gizmo_dragging:
            return
        event = event_callback.getEvent()
        position = event.getPosition()
        size = self.view.getSize()
        screen = (float(position[0]), float(size[1] - position[1]))
        self._set_hover_bone(self._pick_bone(screen))

    def _mouse_event(self, event_callback):
        coin = self._coin()
        event = event_callback.getEvent()
        if event.getState() != coin.SoMouseButtonEvent.DOWN:
            return
        if event.getButton() != coin.SoMouseButtonEvent.BUTTON1:
            return
        if self._gizmo_dragging:
            return
        position = event.getPosition()
        size = self.view.getSize()
        screen = (float(position[0]), float(size[1] - position[1]))
        best = self._pick_bone(screen, include_joint_fallback=True)
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
        root.addLayout(header)

        presets = QtWidgets.QHBoxLayout()
        presets.setSpacing(2)
        self.preset_group = QtWidgets.QButtonGroup(self.form)
        self.preset_buttons = {}
        for preset, label in self.PRESETS:
            button = QtWidgets.QToolButton()
            button.setText(label)
            button.setAutoRaise(True)
            button.setToolTip("Stage the {} starting pose.".format(label.lower()))
            self.preset_group.addButton(button)
            self.preset_buttons[preset] = button
            presets.addWidget(button)
            button.clicked.connect(lambda checked=False, value=preset: self._select_preset(value))
        presets.addStretch(1)
        root.addLayout(presets)

        tool_row = QtWidgets.QHBoxLayout()
        self.symmetry = QtWidgets.QToolButton()
        self.symmetry.setText("Mirror")
        self.symmetry.setCheckable(True)
        self.symmetry.setChecked(False)
        self.symmetry.setAutoRaise(True)
        self.symmetry.setToolTip(
            "Mirror left/right joint rotations across the mannequin center line."
        )
        self.angle_snap = QtWidgets.QToolButton()
        self.angle_snap.setText("5° Snap")
        self.angle_snap.setCheckable(True)
        self.angle_snap.setChecked(False)
        self.angle_snap.setAutoRaise(True)
        self.angle_snap.setToolTip("Snap dragged rotations to 5 degree increments.")
        tool_row.addWidget(self.symmetry)
        tool_row.addWidget(self.angle_snap)
        tool_row.addStretch(1)
        root.addLayout(tool_row)

        selected = QtWidgets.QGroupBox("Selected joint")
        selected_layout = QtWidgets.QVBoxLayout(selected)
        self.selected_label = QtWidgets.QLabel("Select a bone in the 3D view.")
        self.selected_label.setStyleSheet("font-weight: bold;")
        selected_layout.addWidget(self.selected_label)

        self.instruction_label = QtWidgets.QLabel(
            "Click a bone to select it. Drag a colored ring to rotate that axis."
        )
        self.instruction_label.setWordWrap(True)
        selected_layout.addWidget(self.instruction_label)

        axis_row = QtWidgets.QHBoxLayout()
        self._angle_labels = {}
        for axis in ("x", "y", "z"):
            value = QtWidgets.QLabel("{} 0°".format(axis.upper()))
            value.setAlignment(QtCore.Qt.AlignCenter)
            axis_row.addWidget(value, 1)
            self._angle_labels[axis] = value
        selected_layout.addLayout(axis_row)

        self.precision = QtWidgets.QToolButton()
        self.precision.setText("Exact angles…")
        self.precision.setCheckable(True)
        self.precision.setChecked(False)
        self.precision.setArrowType(QtCore.Qt.RightArrow)
        self.precision.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
        selected_layout.addWidget(self.precision)

        self.precision_fields = {}
        precision_widget = QtWidgets.QWidget()
        precision_layout = QtWidgets.QHBoxLayout(precision_widget)
        precision_layout.setContentsMargins(0, 0, 0, 0)
        for axis in ("x", "y", "z"):
            box = QtWidgets.QDoubleSpinBox()
            box.setRange(-180.0, 180.0)
            box.setDecimals(1)
            box.setSuffix("°")
            box.setPrefix("{} ".format(axis.upper()))
            self.precision_fields[axis] = box
            precision_layout.addWidget(box)
            box.valueChanged.connect(lambda value, axis=axis: self._precision_changed(axis, value))
        selected_layout.addWidget(precision_widget)
        self.precision_widget = precision_widget
        self.precision_widget.setVisible(False)
        self.precision.toggled.connect(self._toggle_precision)
        root.addWidget(selected)

        joint_toggle_row = QtWidgets.QHBoxLayout()
        self.joint_list_toggle = QtWidgets.QToolButton()
        self.joint_list_toggle.setText("Joint list")
        self.joint_list_toggle.setCheckable(True)
        self.joint_list_toggle.setChecked(False)
        self.joint_list_toggle.setArrowType(QtCore.Qt.RightArrow)
        self.joint_list_toggle.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
        joint_toggle_row.addWidget(self.joint_list_toggle)
        joint_toggle_row.addStretch(1)
        root.addLayout(joint_toggle_row)

        joint_list_widget = QtWidgets.QWidget()
        joint_list_layout = QtWidgets.QVBoxLayout(joint_list_widget)
        joint_list_layout.setContentsMargins(0, 0, 0, 0)
        self.joints = QtWidgets.QTreeWidget()
        self.joints.setHeaderHidden(True)
        self.joints.setRootIsDecorated(True)
        self.joints.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self._populate_joints()
        joint_list_layout.addWidget(self.joints)
        root.addWidget(joint_list_widget)
        self.joint_list_widget = joint_list_widget
        self.joint_list_widget.setVisible(False)
        self.joint_list_toggle.toggled.connect(self._toggle_joint_list)

        action_row = QtWidgets.QHBoxLayout()
        self.reset_button = QtWidgets.QPushButton("Reset pose")
        self.reset_button.setToolTip(
            "Clear manual joint rotations and return to the active preset baseline."
        )
        action_row.addWidget(self.reset_button)
        action_row.addStretch(1)
        root.addLayout(action_row)

        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        self._staged_joint_rotations = {}
        self._staged_pose_preset = "standing"
        self._loading = True
        self._load()
        self._loading = False

        self.joints.currentItemChanged.connect(self._joint_item_changed)
        self.reset_button.clicked.connect(self._reset_pose)

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
            if (
                bone.endswith(".L")
                and "leg" not in bone
                and any(token in bone for token in ("clavicle", "arm", "wrist"))
            ):
                groups["Left arm"].append((bone, label))
            elif (
                bone.endswith(".R")
                and "leg" not in bone
                and any(token in bone for token in ("clavicle", "arm", "wrist"))
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
            top.setExpanded(False)

    def _load(self):
        if self.avatar is None:
            self.status.setText("Create a Cloth Human Mannequin first.")
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
        self._select_first_joint()

    def _select_first_joint(self):
        for index in range(self.joints.topLevelItemCount()):
            top = self.joints.topLevelItem(index)
            if top.childCount():
                item = top.child(0)
                self.joints.setCurrentItem(item)
                bone = item.data(0, self.QtCore.Qt.UserRole)
                if bone:
                    self._select_joint_without_preview(str(bone))
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
        values = (
            (0.0, 0.0, 0.0)
            if rotation is None
            else (
                float(rotation.x),
                float(rotation.y),
                float(rotation.z),
            )
        )
        for axis, value in zip(("x", "y", "z"), values, strict=False):
            self._set_axis_value(axis, value)

    @staticmethod
    def _joint_label(bone):
        from freecad_cloth.avatar.SkeletonPose import JOINT_LABELS

        return JOINT_LABELS.get(str(bone), str(bone))

    def _set_axis_value(self, axis, value):
        value = float(value)
        label = self._angle_labels[axis]
        precision = self.precision_fields[axis]
        label.setText("{} {:.1f}°".format(axis.upper(), value))
        precision.blockSignals(True)
        precision.setValue(value)
        precision.blockSignals(False)

    def _precision_changed(self, axis, value):
        if self._loading or not getattr(self, "skeleton_joint_index", None):
            return
        values = {}
        for key in ("x", "y", "z"):
            values[key] = float(value) if key == axis else float(self.precision_fields[key].value())
        self._stage_joint_rotation(
            self.skeleton_joint_index,
            values["x"],
            values["y"],
            values["z"],
            preview=True,
            snap=False,
        )

    def _stage_joint_rotation(self, bone, x, y, z, preview=False, snap=None):
        from freecad_cloth.avatar.SkeletonPose import JointRotation

        values = dict(self._staged_joint_rotations)
        rotation = JointRotation(str(bone), float(x), float(y), float(z)).validate()
        if snap is None:
            snap = self.angle_snap.isChecked()
        if snap:
            rotation = JointRotation(
                rotation.bone,
                round(rotation.x / 5.0) * 5.0,
                round(rotation.y / 5.0) * 5.0,
                round(rotation.z / 5.0) * 5.0,
            )
        values[rotation.bone] = rotation
        if self.symmetry.isChecked():
            mirrored = rotation.mirrored()
            if mirrored.bone != rotation.bone:
                values[mirrored.bone] = mirrored
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
        from freecad_cloth.avatar.AvatarCommands import _parameters
        from freecad_cloth.avatar.AvatarModel import AvatarParameters, Pose

        stored = _parameters(self.avatar)
        measurements = dict(stored.measurements)
        preset = str(getattr(self, "_staged_pose_preset", stored.pose.preset))
        arm_angles = getattr(
            self,
            "_staged_arm_angles",
            {
                "left_arm_angle": float(stored.pose.left_arm_angle),
                "right_arm_angle": float(stored.pose.right_arm_angle),
            },
        )
        current_pose = Pose(
            preset,
            float(arm_angles["left_arm_angle"]),
            float(arm_angles["right_arm_angle"]),
            float(stored.pose.left_elbow_angle),
            float(stored.pose.right_elbow_angle),
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
        from freecad_cloth.avatar.AvatarModel import Pose

        defaults = Pose(str(preset))
        self._staged_joint_rotations = {}
        self._staged_pose_preset = str(preset)
        self._staged_arm_angles = {
            "left_arm_angle": float(defaults.left_arm_angle),
            "right_arm_angle": float(defaults.right_arm_angle),
        }
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
            self.controller.refresh_overlay(
                keep_gizmo=bool(
                    self.controller.gizmo is not None and self.controller.gizmo.isActive
                )
            )
        except (AttributeError, RuntimeError, TypeError, ValueError):
            self.status.setText("Preview unavailable; the staged values remain editable.")

    def _reset_pose(self):
        from freecad_cloth.avatar.AvatarModel import Pose

        self._staged_joint_rotations = {}
        self._staged_pose_preset = str(getattr(self.avatar, "PosePreset", "standing"))
        defaults = Pose(self._staged_pose_preset)
        self._staged_arm_angles = {
            "left_arm_angle": float(defaults.left_arm_angle),
            "right_arm_angle": float(defaults.right_arm_angle),
        }
        self._preview_rebuild()
        self._select_first_joint()
        self.status.setText("Pose reset to the selected preset baseline.")

    def _toggle_precision(self, expanded):
        self.precision.setArrowType(
            self.QtCore.Qt.DownArrow if expanded else self.QtCore.Qt.RightArrow
        )
        self.precision_widget.setVisible(bool(expanded))

    def _toggle_joint_list(self, expanded):
        self.joint_list_toggle.setArrowType(
            self.QtCore.Qt.DownArrow if expanded else self.QtCore.Qt.RightArrow
        )
        self.joint_list_widget.setVisible(bool(expanded))

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
        buttons = QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        return int(getattr(buttons, "value", buttons))

    def modifyStandardButtons(self, button_box):
        _, _, _, QtWidgets = _modules()
        ok = button_box.button(QtWidgets.QDialogButtonBox.Ok)
        if ok is not None:
            ok.setText("Apply & Rebuild")


def show_avatar_pose_task(avatar=None):
    """Open the focused Pose Mode task panel."""
    _App, Gui, _QtCore, _QtWidgets = _modules()
    panel = AvatarPoseTaskPanel(avatar)
    Gui.Control.showDialog(panel)
    return panel
