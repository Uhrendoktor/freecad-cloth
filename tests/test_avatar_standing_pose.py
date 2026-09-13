import unittest

from freecad_cloth.avatar.AvatarModel import AvatarParameters, Pose
from freecad_cloth.avatar import _standing_visual_parameters


class AvatarStandingPoseTests(unittest.TestCase):
    def test_legacy_standing_default_is_rendered_neutral(self):
        params = AvatarParameters()
        visual = _standing_visual_parameters(params)
        self.assertEqual(params.pose.left_arm_angle, 12.0)
        self.assertEqual(params.pose.right_arm_angle, 12.0)
        self.assertEqual(visual.pose.left_arm_angle, 70.0)
        self.assertEqual(visual.pose.right_arm_angle, 70.0)
        self.assertEqual(visual.pose.preset, "standing")

    def test_explicit_standing_pose_is_preserved(self):
        params = AvatarParameters(pose=Pose("standing", 35.0, 40.0, 0.0, 0.0))
        visual = _standing_visual_parameters(params)
        self.assertEqual(visual.pose.left_arm_angle, 35.0)
        self.assertEqual(visual.pose.right_arm_angle, 40.0)

    def test_nonstanding_presets_are_preserved(self):
        params = AvatarParameters(pose=Pose("sewing", 12.0, 12.0, 0.0, 0.0))
        visual = _standing_visual_parameters(params)
        self.assertEqual(visual.pose.left_arm_angle, 12.0)
        self.assertEqual(visual.pose.right_arm_angle, 12.0)
        self.assertEqual(visual.pose.preset, "sewing")


if __name__ == "__main__":
    unittest.main()
