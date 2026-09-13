import unittest

from freecad_cloth.avatar import _weighted_medial_root
from freecad_cloth.avatar.AvatarModel import AvatarParameters
from freecad_cloth.avatar.HumanoidMesh import _estimate_shoulder_pivots


class AvatarShoulderPoseTests(unittest.TestCase):
    def test_weighted_medial_root_tracks_proximal_upper_arm(self):
        shoulder_half = 220.0
        samples = [
            (148.0, 1335.0, 0.95),
            (154.0, 1340.0, 0.90),
            (176.0, 1342.0, 0.70),
            (210.0, 1320.0, 0.55),
            (280.0, 1280.0, 0.90),
        ]
        root = _weighted_medial_root(samples, shoulder_half)
        self.assertIsNotNone(root)
        self.assertGreater(root, shoulder_half * 0.55)
        self.assertLess(root, shoulder_half * 0.80)

    def test_shoulder_pivot_follows_medial_arm_root_not_measurement_width(self):
        height = 1750.0
        shoulder_half = 220.0
        shoulder_z = height * 0.76
        vertices = []
        for side in (-1.0, 1.0):
            for lateral in (175.0, 182.0, 188.0, 240.0, 300.0):
                vertices.append((side * lateral, 0.0, shoulder_z))
            for lateral in (180.0, 220.0, 290.0):
                vertices.append((side * lateral, 40.0, height * 0.73))

        pivots = _estimate_shoulder_pivots(vertices, shoulder_half, shoulder_z, height)

        self.assertGreater(abs(pivots[-1]), shoulder_half * 0.70)
        self.assertLess(abs(pivots[-1]), shoulder_half * 0.95)
        self.assertAlmostEqual(pivots[-1], -pivots[1], delta=1e-9)

    def test_avatar_parameters_still_validate_with_pose_defaults(self):
        params = AvatarParameters()
        self.assertEqual(params.pose.preset, "standing")
        self.assertEqual(float(params.pose.left_arm_angle), 12.0)
        self.assertEqual(float(params.pose.right_arm_angle), 12.0)


if __name__ == "__main__":
    unittest.main()
