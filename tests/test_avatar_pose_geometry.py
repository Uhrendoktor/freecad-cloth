"""Regression tests for articulated HM08 arm posing."""
import unittest

from freecad_cloth.avatar.HumanoidMesh import _arm_pose_weight


class AvatarPoseGeometryTests(unittest.TestCase):
    def test_arm_influence_includes_lower_hanging_hand(self):
        shoulder_half = 220.0
        height_mm = 1750.0
        self.assertGreater(_arm_pose_weight(260.0, 850.0, shoulder_half, height_mm), 0.0)
        self.assertGreater(_arm_pose_weight(260.0, 650.0, shoulder_half, height_mm), 0.0)
        self.assertGreater(_arm_pose_weight(260.0, 550.0, shoulder_half, height_mm), 0.0)

    def test_arm_influence_is_zero_inside_torso(self):
        self.assertEqual(_arm_pose_weight(150.0, 1100.0, 220.0, 1750.0), 0.0)


if __name__ == "__main__":
    unittest.main()
