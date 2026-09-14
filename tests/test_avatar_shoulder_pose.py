import unittest

from freecad_cloth.avatar.AvatarModel import AvatarParameters
from freecad_cloth.avatar.HumanoidMesh import (
    MAKEHUMAN_SKELETON_SIZE,
    MAKEHUMAN_SKELETON_URL,
    load_makehuman_skeleton,
)


class AvatarShoulderPoseTests(unittest.TestCase):
    def test_pinned_skeleton_asset_is_present_and_versioned(self):
        self.assertTrue(MAKEHUMAN_SKELETON_URL.endswith("/makehuman/data/rigs/default.mhskel"))
        self.assertEqual(MAKEHUMAN_SKELETON_SIZE, 117790)

    def test_authored_shoulder_chain_has_expected_parentage(self):
        skeleton = load_makehuman_skeleton()
        bones = skeleton["bones"]
        self.assertEqual(bones["shoulder01.L"]["parent"], "clavicle.L")
        self.assertEqual(bones["upperarm01.L"]["parent"], "shoulder01.L")
        self.assertEqual(bones["upperarm02.L"]["parent"], "upperarm01.L")
        self.assertEqual(bones["lowerarm01.L"]["parent"], "upperarm02.L")
        self.assertEqual(bones["lowerarm02.L"]["parent"], "lowerarm01.L")

    def test_avatar_parameters_still_validate_with_pose_defaults(self):
        params = AvatarParameters()
        self.assertEqual(params.pose.preset, "standing")
        self.assertEqual(float(params.pose.left_arm_angle), 12.0)
        self.assertEqual(float(params.pose.right_arm_angle), 12.0)


if __name__ == "__main__":
    unittest.main()
