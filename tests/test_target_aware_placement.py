import unittest

from freecad_cloth.avatar.AvatarCollision import CollisionSurface
from freecad_cloth.avatar.TargetAwarePlacement import (
    TargetPlacementError,
    minimum_signed_clearance,
    probe_target,
    solve_rigid_translation,
    tunic_anchor_profile,
)


def _cube_surface():
    v = (
        (-50.0, -50.0, -50.0), (50.0, -50.0, -50.0), (50.0, 50.0, -50.0), (-50.0, 50.0, -50.0),
        (-50.0, -50.0, 50.0), (50.0, -50.0, 50.0), (50.0, 50.0, 50.0), (-50.0, 50.0, 50.0),
    )
    t = (
        (0, 3, 2), (0, 2, 1),  # bottom
        (4, 5, 6), (4, 6, 7),  # top
        (0, 1, 5), (0, 5, 4),  # front (-Y)
        (1, 2, 6), (1, 6, 5),  # right (+X)
        (2, 3, 7), (2, 7, 6),  # back (+Y)
        (3, 0, 4), (3, 4, 7),  # left (-X)
    )
    return CollisionSurface(v, t, "cube", 2.0)


class TargetAwarePlacementTests(unittest.TestCase):
    def test_tunic_profile_has_deterministic_shoulder_side_and_waist_anchors(self):
        profile = tunic_anchor_profile(500.0, 700.0, "front")
        self.assertEqual(
            tuple(anchor.name for anchor in profile.anchors),
            ("shoulder_left", "shoulder_right", "side_left", "side_right", "waist"),
        )
        self.assertEqual(profile.anchors[0].wrap_direction, "left")
        self.assertEqual(profile.anchors[1].wrap_direction, "right")
        self.assertEqual(profile.anchors[-1].wrap_direction, "front")

    def test_front_probe_is_outward_and_clearance_is_positive(self):
        surface = _cube_surface()
        probe = probe_target(surface, (0.0, -65.0, 0.0), "front")
        self.assertLess(probe.normal[1], -0.9)
        self.assertAlmostEqual(probe.distance, 15.0, places=6)
        self.assertAlmostEqual(minimum_signed_clearance(((0.0, -65.0, 0.0),), surface), 13.0, places=6)

    def test_negative_inside_clearance_is_reported(self):
        surface = _cube_surface()
        clearance = minimum_signed_clearance(((0.0, -49.0, 0.0),), surface)
        self.assertLess(clearance, 0.0)

    def test_rigid_translation_is_deterministic_and_bounded(self):
        surface = _cube_surface()
        profile = tunic_anchor_profile(80.0, 100.0, "front")
        anchors = {
            anchor.name: (
                10.0 if "right" in anchor.name else -10.0 if "left" in anchor.name else 0.0,
                -70.0,
                20.0 if "shoulder" in anchor.name else -20.0,
            )
            for anchor in profile.anchors
        }
        first = solve_rigid_translation(
            anchors, profile, surface, clearance=4.0, max_translation=40.0, max_rotation_degrees=10.0
        )
        second = solve_rigid_translation(
            anchors, profile, surface, clearance=4.0, max_translation=40.0, max_rotation_degrees=10.0
        )
        self.assertEqual(first.translation, second.translation)
        self.assertEqual(first.rotation_degrees, 0.0)
        self.assertGreaterEqual(first.minimum_anchor_clearance, 4.0)

    def test_rigid_translation_rejects_out_of_bound_transform(self):
        surface = _cube_surface()
        profile = tunic_anchor_profile(80.0, 100.0, "front")
        anchors = {anchor.name: (0.0, -200.0, 0.0) for anchor in profile.anchors}
        with self.assertRaises(TargetPlacementError):
            solve_rigid_translation(
                anchors, profile, surface, clearance=4.0, max_translation=20.0, max_rotation_degrees=10.0
            )

    def test_ambiguous_surface_tie_can_be_fail_closed_for_placement(self):
        surface = CollisionSurface(
            (
                (-20.0, -10.0, -20.0), (20.0, -10.0, -20.0), (0.0, -10.0, 20.0),
                (-20.0, -10.0, -20.0), (0.0, -10.0, 20.0), (20.0, 0.0, 0.0),
            ),
            ((0, 1, 2), (3, 4, 5)),
            "ambiguous",
            0.0,
        )
        with self.assertRaises(TargetPlacementError):
            probe_target(surface, (0.0, -30.0, 0.0), "front", ambiguity_tolerance=100.0)

if __name__ == "__main__":
    unittest.main()
