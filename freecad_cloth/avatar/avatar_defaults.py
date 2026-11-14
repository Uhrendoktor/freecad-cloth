# Copyright (C) 2026 FreeCAD Cloth contributors
"""Dependency-neutral anthropometric and pose defaults for the avatar domain."""

DEFAULT_MEASUREMENTS: dict[str, float] = {
    "height": 1750.0,
    "neck": 380.0,
    "shoulder": 440.0,
    "chest": 980.0,
    "underbust": 850.0,
    "waist": 820.0,
    "high_hip": 900.0,
    "hip": 1020.0,
    "upper_arm": 310.0,
    "elbow": 270.0,
    "wrist": 170.0,
    "thigh": 570.0,
    "knee": 390.0,
    "calf": 380.0,
    "ankle": 230.0,
    "inseam": 800.0,
    "torso": 450.0,
    "front_waist": 430.0,
    "back_waist": 440.0,
    "stomach": 950.0,
    "sleeve_length": 630.0,
    "crotch_length": 720.0,
    "front_rise": 280.0,
    "back_rise": 390.0,
    "shirt_length": 700.0,
    "back_neck_to_waist": 450.0,
}

DEFAULT_POSE_ARM_ANGLES: dict[str, float] = {
    "standing": 70.0,
    "sewing": 55.0,
    "sitting": 25.0,
    "t_pose": 12.0,
}
