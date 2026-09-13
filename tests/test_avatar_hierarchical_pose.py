import json
import tempfile
import unittest
from pathlib import Path

from freecad_cloth.avatar.HierarchicalPose import (
    _blend_weighted_pose,
    _group_weights,
)


class AvatarHierarchicalPoseTests(unittest.TestCase):
    def test_group_weights_separate_clavicle_from_arm_chain(self):
        payload = {
            "weights": {
                "clavicle.L": [[1, 0.40]],
                "upperarm01.L": [[1, 0.25]],
                "lowerarm01.L": [[1, 0.35]],
                "finger2-1.L": [[1, 0.10]],
                "spine03": [[1, 1.0]],
                "upperarm01.R": [[2, 0.70]],
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "weights.mhw"
            path.write_text(json.dumps(payload), encoding="utf-8")
            from freecad_cloth.avatar.HierarchicalPose import _group_weights as load
            groups = load(4, str(path))

        self.assertAlmostEqual(groups["clavicle_l"][1], 0.40)
        self.assertAlmostEqual(groups["arm_l"][1], 0.70)
        self.assertAlmostEqual(groups["arm_r"][2], 0.70)
        self.assertEqual(groups["clavicle_r"][2], 0.0)

    def test_rigid_arm_transform_preserves_distance_to_shoulder(self):
        point = (300.0, 0.0, 1300.0)
        posed = _blend_weighted_pose(
            point,
            1.0,
            0.0,
            (170.0, 1330.0),
            (100.0, 1330.0),
            0.2,
            0.0,
        )
        rest = ((point[0] - 170.0) ** 2 + (point[2] - 1330.0) ** 2) ** 0.5
        actual = ((posed[0] - 170.0) ** 2 + (posed[2] - 1330.0) ** 2) ** 0.5
        self.assertAlmostEqual(actual, rest, places=6)

    def test_weighted_shoulder_transition_stays_bounded(self):
        point = (200.0, 0.0, 1300.0)
        posed = _blend_weighted_pose(
            point,
            0.55,
            0.30,
            (170.0, 1330.0),
            (90.0, 1330.0),
            0.2,
            0.07,
        )
        self.assertTrue(all(abs(value) < 5000.0 for value in posed))


if __name__ == "__main__":
    unittest.main()
