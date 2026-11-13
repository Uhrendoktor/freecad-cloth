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
    assert '"axis-rings-cones"' in source
    assert "ClothPoseRotationX" in source
    assert "ClothPoseRotationY" in source
    assert "ClothPoseRotationZ" in source
    assert "coin.SoTrackballDragger()" in source


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
