# Copyright (C) 2026 FreeCAD Cloth contributors
"""Behavioral contract checks for the avatar task-panel boundary.

The expensive visual behavior is covered by FreeCAD acceptance tests. These tests
exercise exported panel configuration and pure helper behavior without reading
the GUI implementation source.
"""

import math
from dataclasses import fields

from freecad_cloth.avatar import AvatarCommands
from freecad_cloth.avatar.AvatarGui import AvatarTaskPanel
from freecad_cloth.avatar.AvatarModel import AvatarParameters, DEFAULT_MEASUREMENTS, Pose
from freecad_cloth.avatar.AvatarProperties import (
    POSE_PROPERTY_MAP,
    PROPERTY_MAP,
    SHAPE_PROPERTY_MAP,
)
from tests.support.assertions import require


def test_avatar_panel_property_mapping_matches_command_authority():
    assert AvatarTaskPanel.PROPERTY_MAP == AvatarCommands.PROPERTY_MAP
    assert set(AvatarTaskPanel.PROPERTY_MAP) == set(AvatarCommands.DEFAULT_MEASUREMENTS)


def test_avatar_panel_groups_cover_all_editable_measurements():
    grouped = tuple(key for key, _label in AvatarTaskPanel.BODY + AvatarTaskPanel.PROPORTIONS)
    assert len(grouped) == len(set(grouped))
    assert set(grouped) == set(AvatarCommands.DEFAULT_MEASUREMENTS)


def test_avatar_panel_shape_fields_match_persistent_command_properties():
    assert AvatarTaskPanel.SHAPE_PROPERTY_MAP == AvatarCommands.SHAPE_PROPERTY_MAP
    assert AvatarTaskPanel.SHAPE_PROPERTY_MAP == {
        "gender": "Gender",
        "breast_size": "BreastSize",
    }
    assert callable(AvatarTaskPanel._shape_changed)
    assert callable(AvatarTaskPanel._toggle_dimension_gizmo)


def test_parent_panel_has_no_duplicate_pose_state():
    """Keep posing in the dedicated editor rather than hidden parent-panel controls."""
    from freecad_cloth.avatar.AvatarPoseGui import AvatarPoseTaskPanel

    assert not hasattr(AvatarTaskPanel, "POSE_FIELDS")
    assert not hasattr(AvatarTaskPanel, "_pose_property")
    assert not hasattr(AvatarTaskPanel, "_rebuild_geometry")
    assert ("t_pose", "T-pose") in AvatarPoseTaskPanel.PRESETS


def test_avatar_panel_provider_choices_match_authoritative_provider_ids():
    assert tuple(key for key, _label in AvatarTaskPanel.PROVIDERS) == AvatarCommands.PROVIDER_IDS
    assert len(AvatarTaskPanel.PROVIDERS) == len(set(AvatarCommands.PROVIDER_IDS))
    provider_labels = dict(AvatarTaskPanel.PROVIDERS)
    geometry_label = provider_labels["freecad-geometry"].lower()
    assert "surface only" in geometry_label
    assert "skeleton" in geometry_label
    assert "animation" in geometry_label


def test_avatar_panel_exposes_the_public_task_panel_protocol():
    assert callable(AvatarTaskPanel)
    for method in (
        "_add_shape_group",
        "_update_shape_labels",
        "_update_shape_enabled",
        "_staged_parameters",
        "_apply",
        "_open_pose_mode",
        "_update_arrangement_points",
        "_update_landmarks",
    ):
        assert callable(getattr(AvatarTaskPanel, method, None))


def test_viewport_dimension_handle_drag_math_is_scaled_and_clamped():
    from freecad_cloth.avatar.AvatarShapeGui import AvatarDimensionController

    # Ten pixels represents 100 mm along this projected 100 mm axis.
    self_value = AvatarDimensionController._dragged_value(
        1750.0, (5.0, 0.0), (10.0, 0.0), 1.0, (1200.0, 2300.0)
    )
    assert self_value == 1800.0
    circumference = AvatarDimensionController._dragged_value(
        900.0, (15.0, 0.0), (10.0, 0.0), 2.0 * math.pi, (600.0, 1600.0)
    )
    assert circumference == 1600.0
    assert (
        AvatarDimensionController._dragged_value(
            1750.0, (0.0, -10.0), (0.0, -20.0), 1.0, (1200.0, 2300.0)
        )
        == 1800.0
    )


def test_measurement_properties_are_generated_from_model_measurements() -> None:
    """Ensure every canonical measurement has the corresponding persisted property."""
    expected = {
        name: "_".join(part.capitalize() for part in name.split("_"))
        for name in DEFAULT_MEASUREMENTS
    }
    require(
        condition=PROPERTY_MAP == expected,
        message="measurement property names must derive from the AvatarParameters keys",
    )


def test_shape_properties_are_generated_from_model_field_metadata() -> None:
    """Ensure shape properties derive from canonical model-field metadata."""
    expected = {
        field.name: "".join(part.capitalize() for part in field.name.split("_"))
        for field in fields(AvatarParameters)
        if field.metadata.get("freecad_property_group") == "shape"
    }
    require(
        condition=expected == {"gender": "Gender", "breast_size": "BreastSize"},
        message="shape fields must carry stable FreeCAD grouping metadata on the model.",
    )
    require(
        condition=SHAPE_PROPERTY_MAP == expected,
        message="shape property names must be derived from AvatarParameters field metadata.",
    )


def test_pose_properties_cover_all_pose_angle_fields() -> None:
    """Ensure FreeCAD pose properties track every angle field on the Pose model."""
    expected = {
        field.name: "".join(part.capitalize() for part in field.name.split("_"))
        for field in fields(Pose)
        if field.name.endswith("_angle")
    }
    require(
        condition=POSE_PROPERTY_MAP == expected,
        message="pose property names must derive from the Pose angle fields",
    )
