# Copyright (C) 2026 FreeCAD Cloth contributors
"""Behavioral checks for the focused mannequin Pose Mode controller."""

from dataclasses import fields

from freecad_cloth.avatar.AvatarModel import Pose
from freecad_cloth.avatar.AvatarPoseGui import AvatarPoseTaskPanel, SkeletonPoseController
from freecad_cloth.avatar.AvatarProperties import POSE_PROPERTY_MAP
from freecad_cloth.avatar.SkeletonPose import (
    CONTROLLABLE_BONES,
    CONTROLLABLE_JOINTS,
    JOINT_LABELS,
)


def test_pose_controller_screen_distance_handles_interior_projection():
    distance = SkeletonPoseController._screen_segment_distance
    assert distance((5.0, 0.0), (0.0, 0.0), (10.0, 0.0)) == 0.0
    assert distance((5.0, 3.0), (0.0, 0.0), (10.0, 0.0)) == 3.0


def test_pose_controller_screen_distance_clamps_to_segment_endpoints():
    distance = SkeletonPoseController._screen_segment_distance
    assert distance((20.0, 0.0), (0.0, 0.0), (10.0, 0.0)) == 10.0
    assert distance((-5.0, 0.0), (0.0, 0.0), (10.0, 0.0)) == 5.0


def test_pose_controller_screen_distance_handles_degenerate_segments():
    distance = SkeletonPoseController._screen_segment_distance
    assert distance((8.0, 12.0), (5.0, 5.0), (5.0, 5.0)) == 7.615773105863909


def test_pose_controller_exposes_bounded_gizmo_constants():
    assert SkeletonPoseController.GIZMO_SIZE > 0
    assert SkeletonPoseController.BONE_PICK_RADIUS > 0
    assert SkeletonPoseController.JOINT_PICK_RADIUS > SkeletonPoseController.BONE_PICK_RADIUS


def test_pose_mode_uses_canonical_pose_and_skeleton_catalogues():
    pose_fields = tuple(field.name for field in fields(Pose) if field.name.endswith("_angle"))
    assert pose_fields == (
        "left_arm_angle",
        "right_arm_angle",
        "left_elbow_angle",
        "right_elbow_angle",
    )
    assert tuple(POSE_PROPERTY_MAP) == pose_fields
    assert AvatarPoseTaskPanel.PRESETS == (
        ("t_pose", "T-pose"),
        ("standing", "Standing"),
        ("sewing", "Sewing"),
        ("sitting", "Sitting"),
    )
    assert tuple(JOINT_LABELS.items()) == CONTROLLABLE_JOINTS
    assert tuple(bone for bone, _label in CONTROLLABLE_JOINTS) == CONTROLLABLE_BONES


def test_pose_mode_keeps_xyz_fields_visible_and_bidirectionally_linked() -> None:
    """Keep exact angle controls visible and expose field-to-ring highlighting."""
    assert callable(AvatarPoseTaskPanel._set_rotation_axis_highlight)
    assert callable(SkeletonPoseController.highlight_axis)


def test_pose_mode_helpers_are_runtime_importable_without_freecad_gui():
    import freecad_cloth.avatar.AvatarPoseGui as pose_gui

    assert callable(pose_gui.joint_world_positions)
    assert callable(pose_gui.skeleton_world_segments)
    assert callable(pose_gui.show_avatar_pose_task)


def test_pose_mode_uses_native_axis_rotation_gizmo():
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1] / "freecad_cloth" / "avatar" / "AvatarPoseGui.py"
    ).read_text(encoding="utf-8")
    assert 'coin.SoType.fromName("SoRotationDragger")' in source
    assert 'coin.SoType.fromName("SoRotatorGeometry2")' in source
    assert "_configure_axis_rotation_dragger" in source
    assert '"axis-rings-camera"' in source
    assert '"axis-rings-cones"' in source
    assert 'coin.SoType.fromName("SoVRMLBillboard")' in source
    assert '"ClothPoseRotationView"' in source
    assert "camera_facing=True" in source
    assert "ClothPoseRotationX" in source
    assert "ClothPoseRotationY" in source
    assert "ClothPoseRotationZ" in source
    assert "axis_branch = coin.SoSeparator()" in source
    assert "axis_branch.addChild(dragger)" in source
    assert 'self.gizmo_mode = "fallback-panel"' in source
    assert "self._create_fallback_gizmo(bone)" in source
    assert "self.precision_widget.setVisible(True)" in source


def test_avatar_panel_initializes_preset_loading_guard_before_loading():
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1] / "freecad_cloth" / "avatar" / "AvatarGui.py"
    ).read_text(encoding="utf-8")
    initialization = source.split("def __init__(self, avatar=None):", 1)[1].split(
        "def _open_pose_mode", 1
    )[0]
    assert "self._loading = True" in initialization
    assert "finally:" in initialization
    assert "self._loading = False" in initialization
    assert initialization.index("self._loading = True") < initialization.index("self._load()")
    assert initialization.index("self._load()") < initialization.index("self._loading = False")


def test_pose_ui_acceptance_drives_native_rotation_ring_with_real_viewport_input() -> None:
    from pathlib import Path

    acceptance = (
        Path(__file__).resolve().parents[1] / "tests" / "freecad_avatar_pose_ui_acceptance.py"
    ).read_text(encoding="utf-8")
    assert "def _drag_native_pose_ring" in acceptance
    assert "viewport_widget(Gui, view)" in acceptance
    assert "mouse_press(viewport, start" in acceptance
    assert "mouse_move(" in acceptance
    assert "mouse_release(viewport, end" in acceptance
    assert "wait_until(" in acceptance and "_gizmo_dragging" in acceptance
    assert "pose-ring-drag=passed" in acceptance


def test_pose_mouse_down_does_not_rebuild_the_selected_dragger_branch() -> None:
    from types import SimpleNamespace

    controller = SkeletonPoseController.__new__(SkeletonPoseController)
    controller.view = SimpleNamespace(getSize=lambda: (800, 600))
    controller._gizmo_dragging = False
    controller.selected_bone = "upperarm01.L"
    controller._pick_rotation_ring = lambda _screen: None
    controller._coin = lambda: SimpleNamespace(
        SoMouseButtonEvent=SimpleNamespace(DOWN=1, BUTTON1=1)
    )
    controller._pick_bone = lambda _screen, include_joint_fallback=False: (
        "upperarm01.L" if include_joint_fallback else None
    )
    selected = []
    controller.select_joint = selected.append

    class MouseEvent:
        def getState(self) -> int:
            return 1

        def getButton(self) -> int:
            return 1

        def getPosition(self) -> tuple[int, int]:
            return (400, 300)

    controller._mouse_event(SimpleNamespace(getEvent=lambda: MouseEvent()))

    assert selected == []


def test_mouse_release_finishes_pointer_driven_pose_drag() -> None:
    from types import SimpleNamespace

    controller = SkeletonPoseController.__new__(SkeletonPoseController)
    controller.view = SimpleNamespace(getSize=lambda: (800, 600))
    controller._gizmo_dragging = True
    controller._coin = lambda: SimpleNamespace(
        SoMouseButtonEvent=SimpleNamespace(UP=0, DOWN=1, BUTTON1=1)
    )
    calls = []
    controller._gizmo_finish = lambda _data, _dragger: calls.append("finish")
    event = SimpleNamespace(
        getState=lambda: 0,
        getButton=lambda: 1,
        getPosition=lambda: (400, 300),
    )

    controller._mouse_event(SimpleNamespace(getEvent=lambda: event))

    assert calls == ["finish"]


def test_mouse_down_on_ring_starts_axis_drag_before_bone_selection() -> None:
    from types import SimpleNamespace

    controller = SkeletonPoseController.__new__(SkeletonPoseController)
    controller.view = SimpleNamespace(getSize=lambda: (800, 600))
    controller._gizmo_dragging = False
    controller.selected_bone = "upperarm01.L"
    samples = ((0.0, (400.0, 300.0)), (360.0, (400.0, 300.0)))
    controller._coin = lambda: SimpleNamespace(
        SoMouseButtonEvent=SimpleNamespace(UP=0, DOWN=1, BUTTON1=1)
    )
    controller._pick_rotation_ring = lambda _screen: ("X", 25.0, samples)
    controller._pick_bone = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("ring press should not re-run bone selection")
    )
    started = []
    controller._gizmo_start = lambda _data, axis, angle: started.append((axis, angle))

    event = SimpleNamespace(
        getState=lambda: 1,
        getButton=lambda: 1,
        getPosition=lambda: (400, 300),
    )
    controller._mouse_event(SimpleNamespace(getEvent=lambda: event))

    assert controller._manual_ring_samples == samples
    assert started == [("X", 25.0)]


def test_pointer_angle_is_interpolated_from_projected_ring_segments() -> None:
    samples = (
        (0.0, (90.0, 50.0)),
        (90.0, (50.0, 10.0)),
        (180.0, (10.0, 50.0)),
        (270.0, (50.0, 90.0)),
        (360.0, (90.0, 50.0)),
    )

    distance, angle = SkeletonPoseController._nearest_ring_angle((50.0, 10.0), samples)

    assert distance == 0.0
    assert angle == 90.0


def test_location_events_stage_rotation_without_reading_coin_fields() -> None:
    from types import SimpleNamespace

    controller = SkeletonPoseController.__new__(SkeletonPoseController)
    controller.view = SimpleNamespace(getSize=lambda: (100, 100))
    controller._gizmo_dragging = True
    controller._manual_ring_angle_start = 0.0
    controller._manual_ring_angle_current = None
    controller._manual_ring_samples = (
        (0.0, (90.0, 50.0)),
        (90.0, (50.0, 10.0)),
        (180.0, (10.0, 50.0)),
        (270.0, (50.0, 90.0)),
        (360.0, (90.0, 50.0)),
    )
    staged = []
    controller._gizmo_motion = lambda _data, angle: staged.append(angle)
    event = SimpleNamespace(getPosition=lambda: (50, 90))
    controller._location_event(SimpleNamespace(getEvent=lambda: event))

    assert staged == [90.0]
    assert controller._manual_ring_angle_current == 90.0


def test_pose_dragger_interaction_does_not_poll_coin_swig_fields() -> None:
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1] / "freecad_cloth" / "avatar" / "AvatarPoseGui.py"
    ).read_text(encoding="utf-8")
    assert "_poll_native_dragger_state" not in source
    assert "dragger.isActive.getValue()" not in source
    assert "dragger.rotation.getValue()" not in source
    assert "addStartCallback" not in source
    assert "addMotionCallback" not in source
    assert "addFinishCallback" not in source
    assert "self._nearest_ring_angle(screen, self._manual_ring_samples)" in source
    assert (
        "self._gizmo_motion(None, _normalize_signed_angle_degrees(angle - start_angle))" in source
    )


def test_pose_angle_normalization_wraps_into_joint_limits() -> None:
    from freecad_cloth.avatar.AvatarPoseGui import _normalize_signed_angle_degrees

    assert _normalize_signed_angle_degrees(187.0) == -173.0
    assert _normalize_signed_angle_degrees(-187.0) == 173.0
    assert -180.0 <= _normalize_signed_angle_degrees(541.0) <= 180.0


def test_freecad_yaw_pitch_roll_maps_to_mannequin_xyz_order() -> None:
    from freecad_cloth.avatar.AvatarPoseGui import _pose_xyz_from_yaw_pitch_roll

    assert _pose_xyz_from_yaw_pitch_roll((30.0, -20.0, 10.0)) == (
        10.0,
        -20.0,
        30.0,
    )


def test_pose_drag_defers_mesh_rebuild_until_native_drag_finishes() -> None:
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1] / "freecad_cloth" / "avatar" / "AvatarPoseGui.py"
    ).read_text(encoding="utf-8")
    motion = source.split("def _gizmo_motion", 1)[1].split("def _gizmo_finish", 1)[0]
    finish = source.split("def _gizmo_finish", 1)[1].split("def _clear_hover_overlay", 1)[0]

    assert "preview=False" in motion
    assert "self.panel._preview_rebuild()" in finish


def test_remove_gizmo_clears_manual_ring_state_before_dropping_nodes() -> None:
    controller = SkeletonPoseController.__new__(SkeletonPoseController)
    controller._manual_ring_axis_name = "X"
    controller._manual_ring_angle_start = 15.0
    controller._manual_ring_angle_current = 42.0
    controller._manual_ring_samples = ((0.0, (0.0, 0.0)),)
    controller.gizmo_foreground = None
    controller.gizmo_separator = None
    controller.scene_graph = None
    controller.gizmo_transform = object()
    controller.gizmo = object()
    controller.gizmo_mode = "native"
    controller.gizmo_style = "axis-rings-camera"
    controller.gizmo_style_error = None
    controller._native_dragger = [object()]
    controller._axis_draggers = {"X": object()}
    controller._gizmo_dragging = False

    controller._remove_gizmo()

    assert controller._manual_ring_axis_name is None
    assert controller._manual_ring_angle_start is None
    assert controller._manual_ring_angle_current is None
    assert controller._manual_ring_samples is None
    assert controller._native_dragger is None
    assert controller._axis_draggers == {}


def test_selecting_the_current_pose_joint_does_not_recreate_native_draggers() -> None:
    from types import SimpleNamespace

    panel = SimpleNamespace(_select_joint_without_preview=lambda _bone: None)
    controller = SkeletonPoseController.__new__(SkeletonPoseController)
    controller._positions = {"upperarm01.L": (0.0, 0.0, 0.0)}
    controller.selected_bone = "upperarm01.L"
    controller.gizmo = object()
    controller.panel = panel
    controller._set_hover_bone = lambda _bone: None
    calls = []
    controller._create_gizmo = calls.append
    controller.refresh_overlay = lambda **_kwargs: calls.append("refresh")

    controller.select_joint("upperarm01.L")

    assert calls == []
