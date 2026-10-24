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
