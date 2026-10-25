# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression tests for articulated HM08 arm posing."""

import pytest

from freecad_cloth.avatar.HumanoidMesh import arm_pose_weight


def test_arm_influence_includes_lower_hanging_hand() -> None:
    """Keep the geometric fallback active through the lower hanging hand."""
    shoulder_half = 220.0
    height_mm = 1750.0
    influences = tuple(
        arm_pose_weight(260.0, z, shoulder_half, height_mm)
        for z in (850.0, 650.0, 550.0)
    )
    assert all(influence > 0.0 for influence in influences)


def test_arm_influence_is_zero_inside_torso() -> None:
    """Assign no arm-chain influence to a vertex inside the torso."""
    assert arm_pose_weight(150.0, 1100.0, 220.0, 1750.0) == pytest.approx(0.0)
