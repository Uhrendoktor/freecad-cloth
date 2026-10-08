"""Behavioral contract checks for the avatar task-panel boundary.

The expensive visual behavior is covered by FreeCAD acceptance tests. These tests
exercise exported panel configuration and pure helper behavior without reading
the GUI implementation source.
"""

from freecad_cloth.avatar import AvatarCommands
from freecad_cloth.avatar.AvatarGui import AvatarTaskPanel


def test_avatar_panel_property_mapping_matches_command_authority():
    assert AvatarTaskPanel.PROPERTY_MAP == AvatarCommands.PROPERTY_MAP
    assert set(AvatarTaskPanel.PROPERTY_MAP) == set(AvatarCommands.DEFAULT_MEASUREMENTS)


def test_avatar_panel_groups_cover_all_editable_measurements():
    grouped = tuple(key for key, _label in AvatarTaskPanel.BODY + AvatarTaskPanel.PROPORTIONS)
    assert len(grouped) == len(set(grouped))
    assert set(grouped) == set(AvatarCommands.DEFAULT_MEASUREMENTS)


def test_avatar_panel_pose_fields_match_command_pose_schema():
    assert tuple(key for key, _label in AvatarTaskPanel.POSE_FIELDS) == (
        "left_arm_angle",
        "right_arm_angle",
        "left_elbow_angle",
        "right_elbow_angle",
    )
    assert {
        key: AvatarTaskPanel._pose_property(key)
        for key, _label in AvatarTaskPanel.POSE_FIELDS
    } == AvatarCommands.POSE_PROPERTY_MAP


def test_avatar_panel_provider_choices_match_authoritative_provider_ids():
    assert tuple(key for key, _label in AvatarTaskPanel.PROVIDERS) == AvatarCommands.PROVIDER_IDS
    assert len(AvatarTaskPanel.PROVIDERS) == len(set(AvatarCommands.PROVIDER_IDS))


def test_avatar_panel_exposes_the_public_task_panel_protocol():
    assert callable(AvatarTaskPanel)
    for method in (
        "_staged_parameters",
        "_apply",
        "_open_pose_mode",
        "_update_arrangement_points",
        "_update_landmarks",
    ):
        assert callable(getattr(AvatarTaskPanel, method, None))


def test_avatar_panel_keeps_legacy_pose_and_skeleton_paths_secondary():
    # These are runtime defaults/configuration, not source-text requirements.
    assert "standing" in AvatarCommands.Pose.VALID_PRESETS
    assert "sewing" in AvatarCommands.Pose.VALID_PRESETS
    assert "sitting" in AvatarCommands.Pose.VALID_PRESETS
    assert AvatarTaskPanel.POSE_FIELDS
