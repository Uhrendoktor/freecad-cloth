import json
import tempfile
import unittest
from pathlib import Path

from freecad_cloth.avatar.HumanoidMesh import (
    _arm_pose_weight,
    load_makehuman_arm_weights,
)


class AvatarHipPoseTests(unittest.TestCase):
    def test_hip_region_has_no_arm_pose_influence_without_source_weights(self):
        height = 1750.0
        self.assertEqual(_arm_pose_weight(260.0, height * 0.50, 170.0, height), 0.0)
        self.assertEqual(_arm_pose_weight(-260.0, height * 0.50, -170.0, height), 0.0)

    def test_source_weight_is_authoritative_for_arm_influence(self):
        height = 1750.0
        self.assertEqual(_arm_pose_weight(260.0, height * 0.72, 170.0, height, 0.0), 0.0)
        self.assertEqual(_arm_pose_weight(10.0, height * 0.50, 170.0, height, 1.0), 1.0)
        self.assertAlmostEqual(_arm_pose_weight(10.0, height * 0.50, 170.0, height, 0.35), 0.35)

    def test_makehuman_arm_weights_sum_only_arm_chain_bones(self):
        payload = {
            "weights": {
                "upperarm01.L": [[1, 0.25]],
                "lowerarm01.L": [[1, 0.50]],
                "wrist.L": [[1, 0.20]],
                "finger2-1.L": [[1, 0.10]],
                "shoulder.L": [[1, 0.90]],
                "spine03": [[1, 1.0]],
                "upperarm01.R": [[2, 0.60]],
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "weights.mhw"
            path.write_text(json.dumps(payload), encoding="utf-8")
            left, right = load_makehuman_arm_weights(4, str(path))

        self.assertAlmostEqual(left[1], 1.0)
        self.assertAlmostEqual(right[2], 0.60)
        self.assertEqual(left[0], 0.0)
        self.assertEqual(right[1], 0.0)


if __name__ == "__main__":
    unittest.main()
