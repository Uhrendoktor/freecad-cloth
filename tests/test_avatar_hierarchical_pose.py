import json
import math
import tempfile
import unittest
from pathlib import Path

from freecad_cloth.avatar.HierarchicalPose import (
    _blend_weighted_pose,
    _group_weights,
    _map_weight_groups_to_geometry,
    _signed_angle_xz,
    _shortest_angle,
    _straighten_hands,
    _weighted_distal_direction,
)


class AvatarHierarchicalPoseTests(unittest.TestCase):
    def test_group_weights_separate_clavicle_from_arm_chain(self):
        payload = {
            "weights": {
                "clavicle.L": [[1, 0.40]],
                "upperarm01.L": [[1, 0.25]],
                "lowerarm01.L": [[1, 0.35]],
                "wrist.L": [[1, 0.20]],
                "hand.L": [[1, 0.30]],
                "finger2-1.L": [[1, 0.10]],
                "spine03": [[1, 1.0]],
                "upperarm01.R": [[2, 0.70]],
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "weights.mhw"
            path.write_text(json.dumps(payload), encoding="utf-8")
            groups = _group_weights(4, str(path))

        self.assertAlmostEqual(groups["clavicle_l"][1], 0.40)
        self.assertAlmostEqual(groups["arm_l"][1], 1.0)
        self.assertAlmostEqual(groups["lowerarm_l"][1], 0.35)
        self.assertAlmostEqual(groups["wrist_l"][1], 0.20)
        self.assertAlmostEqual(groups["hand_l"][1], 0.40)
        self.assertAlmostEqual(groups["arm_r"][2], 0.70)
        self.assertEqual(groups["clavicle_r"][2], 0.0)

    def test_weight_groups_follow_physical_x_side_not_rig_label(self):
        vertices = (
            (-220.0, 0.0, 1330.0),
            (220.0, 0.0, 1330.0),
        )
        groups = {
            "arm_l": (0.0, 1.0),
            "arm_r": (1.0, 0.0),
            "clavicle_l": (0.0, 1.0),
            "clavicle_r": (1.0, 0.0),
            "lowerarm_l": (0.0, 1.0),
            "lowerarm_r": (1.0, 0.0),
            "wrist_l": (0.0, 1.0),
            "wrist_r": (1.0, 0.0),
            "hand_l": (0.0, 1.0),
            "hand_r": (1.0, 0.0),
        }
        mapped = _map_weight_groups_to_geometry(vertices, groups)
        for prefix in ("arm", "clavicle", "lowerarm", "wrist", "hand"):
            self.assertEqual(mapped[f"{prefix}_l"], (1.0, 0.0))
            self.assertEqual(mapped[f"{prefix}_r"], (0.0, 1.0))

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

    def test_distal_hand_direction_favors_fingers_over_wrist_base(self):
        vertices = (
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 6.0),
            (0.0, 0.0, 24.0),
        )
        weights = (1.0, 1.0, 0.05)
        direction = _weighted_distal_direction(vertices, weights, (0.0, 0.0), min_distance=2.0)
        self.assertIsNotNone(direction)
        dx, dz = direction
        self.assertAlmostEqual(dx, 0.0, places=6)
        self.assertGreater(dz, 15.0)

    def test_straighten_hands_reduces_large_wrist_kink(self):
        vertices = (
            (200.0, 0.0, 1200.0),  # lower-arm center
            (220.0, 0.0, 1100.0),  # wrist
            (270.0, 0.0, 1130.0),  # near-wrist hand vertices
            (274.0, 0.0, 1148.0),  # distal finger vertices
            (278.0, 0.0, 1165.0),
        )
        posed = list(vertices)
        weights = {
            "lowerarm_l": (1.0, 0.0, 0.0, 0.0, 0.0),
            "wrist_l": (0.0, 1.0, 0.0, 0.0, 0.0),
            "hand_l": (0.0, 0.0, 1.0, 0.45, 0.20),
            "lowerarm_r": (0.0, 0.0, 0.0, 0.0, 0.0),
            "wrist_r": (0.0, 0.0, 0.0, 0.0, 0.0),
            "hand_r": (0.0, 0.0, 0.0, 0.0, 0.0),
        }
        forearm_angle = _signed_angle_xz(20.0, -100.0)
        hand_before = _weighted_distal_direction(vertices, weights["hand_l"], (220.0, 1100.0), min_distance=4.0)
        before = abs(_shortest_angle(forearm_angle, _signed_angle_xz(hand_before[0], hand_before[1])))
        result = _straighten_hands(vertices, posed, weights)
        hand_after = _weighted_distal_direction(result, weights["hand_l"], (220.0, 1100.0), min_distance=4.0)
        after = abs(_shortest_angle(forearm_angle, _signed_angle_xz(hand_after[0], hand_after[1])))
        self.assertLess(after, before)
        self.assertLessEqual(after, math.radians(150.0) + 1e-6)


if __name__ == "__main__":
    unittest.main()
