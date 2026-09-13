import unittest

from freecad_cloth.avatar.HumanoidMesh import _arm_pose_weight


class AvatarHipPoseTests(unittest.TestCase):
    def test_hip_region_has_no_arm_pose_influence(self):
        height = 1750.0
        self.assertEqual(_arm_pose_weight(260.0, height * 0.50, 170.0, height), 0.0)
        self.assertEqual(_arm_pose_weight(-260.0, height * 0.50, -170.0, height), 0.0)

    def test_upper_arm_region_can_receive_pose_influence(self):
        height = 1750.0
        self.assertGreater(_arm_pose_weight(260.0, height * 0.72, 170.0, height), 0.0)


if __name__ == "__main__":
    unittest.main()
