"""Behavioral checks for the focused mannequin Pose Mode controller."""

from freecad_cloth.avatar.AvatarGui import AvatarTaskPanel
from freecad_cloth.avatar.AvatarPoseGui import SkeletonPoseController


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


def test_pose_mode_uses_the_same_pose_fields_as_avatar_editor():
    assert AvatarTaskPanel.POSE_FIELDS == (
        ("left_arm_angle", "Left arm"),
        ("right_arm_angle", "Right arm"),
        ("left_elbow_angle", "Left elbow bend"),
        ("right_elbow_angle", "Right elbow bend"),
    )


def test_pose_mode_helpers_are_runtime_importable_without_freecad_gui():
    import freecad_cloth.avatar.AvatarPoseGui as pose_gui

    assert callable(pose_gui.joint_world_positions)
    assert callable(pose_gui.skeleton_world_segments)
    assert callable(pose_gui.show_avatar_pose_task)
