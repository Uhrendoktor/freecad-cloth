# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression checks for generated FreeCAD avatar property names."""

from dataclasses import fields

from freecad_cloth.avatar.AvatarModel import AvatarParameters, DEFAULT_MEASUREMENTS, Pose
from freecad_cloth.avatar.AvatarProperties import (
    POSE_PROPERTY_MAP,
    PROPERTY_MAP,
    SHAPE_PROPERTY_MAP,
)
from support.assertions import require


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


def test_shape_properties_use_model_field_names() -> None:
    """Keep the persisted shape-property names generated from avatar model fields."""
    field_names = {field.name for field in fields(AvatarParameters)}
    require(
        condition=SHAPE_PROPERTY_MAP == {"gender": "Gender", "breast_size": "BreastSize"}
        and set(SHAPE_PROPERTY_MAP) <= field_names,
        message="shape property names must be generated from the model's shape fields",
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
