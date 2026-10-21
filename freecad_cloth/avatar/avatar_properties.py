# Copyright (C) 2026 FreeCAD Cloth contributors
"""Canonical mappings for avatar parameters and persisted FreeCAD properties.

The command model owns these keys so task panels and pose editors display and
persist the same measurements, shape parameters, pose fields, and providers.
"""

PROPERTY_MAP = {
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
SHAPE_PROPERTY_MAP = {
    "gender": "GenderBlend",
    "breast_size": "BreastSize",
}
POSE_PROPERTY_MAP = {
    "left_arm_angle": "LeftArmAngle",
    "right_arm_angle": "RightArmAngle",
    "left_elbow_angle": "LeftElbowAngle",
    "right_elbow_angle": "RightElbowAngle",
}
PROVIDER_IDS = ("makehuman-hm08", "freecad-geometry")
