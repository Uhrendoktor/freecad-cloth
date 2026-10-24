# Copyright (C) 2026 FreeCAD Cloth contributors
"""Generate FreeCAD property names from the canonical avatar data model.

Measurement property names retain word separators (back_neck_to_waist becomes
Back_Neck_To_Waist). Shape and pose property names use PascalCase without
separators (left_arm_angle becomes LeftArmAngle). The maps are derived from
model fields so adding a measurement or pose angle does not require a second
manually maintained mapping table.
"""

from dataclasses import fields

from freecad_cloth.avatar.AvatarModel import AvatarParameters, DEFAULT_MEASUREMENTS, Pose


def _measurement_property_name(name: str) -> str:
    """Convert an underscore-separated measurement key to its FreeCAD property name.

    Args:
        name: Canonical snake_case key used by AvatarParameters.

    Returns:
        Property name with capitalized parts separated by underscores.
    """
    return "_".join(part.capitalize() for part in name.split("_"))


def _property_name(name: str) -> str:
    """Convert a model field to the PascalCase spelling used by FreeCAD properties.

    Args:
        name: Canonical snake_case model field.

    Returns:
        PascalCase property name without word separators.
    """
    return "".join(part.capitalize() for part in name.split("_"))


PROPERTY_MAP = {
    name: _measurement_property_name(name) for name in DEFAULT_MEASUREMENTS
}
_SHAPE_FIELDS = ("gender", "breast_size")
SHAPE_PROPERTY_MAP = {
    field.name: _property_name(field.name)
    for field in fields(AvatarParameters)
    if field.name in _SHAPE_FIELDS
}
POSE_PROPERTY_MAP = {
    field.name: _property_name(field.name)
    for field in fields(Pose)
    if field.name.endswith("_angle")
}
PROVIDER_IDS = ("makehuman-hm08", "freecad-geometry")
