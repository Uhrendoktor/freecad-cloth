# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression tests for MakeHuman-derived arm fitting and pose inputs."""
import json
import tempfile
import unittest
from pathlib import Path

from freecad_cloth.avatar.HumanoidMesh import (
    _arm_pose_weight,
    _estimate_rest_arm_angles,
    load_makehuman_arm_weights,
)


class AvatarArmPoseTests(unittest.TestCase):
    """Cover source weights and the geometry-based fallback for arm poses."""

    def test_geometric_fallback_covers_lower_arm_envelope_without_source_weights(self):
        """Keep both arm envelopes controllable when source weights are absent."""
        height = 1750.0
        self.assertEqual(_arm_pose_weight(260.0, height * 0.50, 170.0, height), 1.0)
        self.assertEqual(_arm_pose_weight(-260.0, height * 0.50, -170.0, height), 1.0)

    def test_source_weight_is_authoritative_for_arm_influence(self):
        """Honor authored arm weights rather than inferring extra influence."""
        height = 1750.0
        self.assertEqual(_arm_pose_weight(260.0, height * 0.72, 170.0, height, 0.0), 0.0)
        self.assertEqual(_arm_pose_weight(10.0, height * 0.50, 170.0, height, 1.0), 1.0)
        self.assertAlmostEqual(_arm_pose_weight(10.0, height * 0.50, 170.0, height, 0.35), 0.35)


    def test_rest_angle_estimator_vectorizes_geometry_and_respects_weights(self) -> None:
        """Estimate mirrored rest angles and ignore vertices with no arm influence."""
        vertices = (
            (-150.0, 0.0, 600.0),
            (-200.0, 0.0, 700.0),
            (150.0, 0.0, 600.0),
            (200.0, 0.0, 700.0),
            (0.0, 0.0, 900.0),
        )
        pivots = {-1.0: -100.0, 1.0: 100.0}
        angles = _estimate_rest_arm_angles(vertices, pivots, 760.0, 1000.0)
        self.assertGreater(angles[-1.0], 0.0)
        self.assertAlmostEqual(angles[-1.0], angles[1.0])

        zero_weights = ((0.0,) * len(vertices), (0.0,) * len(vertices))
        weighted_angles = _estimate_rest_arm_angles(
            vertices, pivots, 760.0, 1000.0, zero_weights
        )
        self.assertEqual(weighted_angles, {-1.0: 0.0, 1.0: 0.0})

    def test_makehuman_arm_weights_sum_only_arm_chain_bones(self):
        """Accumulate only named arm-chain weights for each side."""
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
