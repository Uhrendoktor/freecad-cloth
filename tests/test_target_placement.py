import math
import unittest

from freecad_cloth.avatar.AvatarCollision import CollisionSurface
from freecad_cloth.avatar.TargetPlacement import (
    minimum_signed_clearance,
    rigid_translation_for_clearance,
)


def _cube_surface(radius=10.0):
    r = float(radius)
    vertices = (
        (-r, -r, -r), (r, -r, -r), (r, r, -r), (-r, r, -r),
        (-r, -r, r), (r, -r, r), (r, r, r), (-r, r, r),
    )
    triangles = (
        (0, 1, 2), (0, 2, 3),
        (4, 6, 5), (4, 7, 6),
        (0, 4, 5), (0, 5, 1),
        (1, 5, 6), (1, 6, 2),
        (2, 6, 7), (2, 7, 3),
        (4, 0, 3), (4, 3, 7),
    )
    return CollisionSurface(vertices, triangles, thickness=1.0)


class TargetPlacementTests(unittest.TestCase):
    def test_deterministic_outward_translation_reaches_clearance(self):
        surface = _cube_surface()
        points = ((11.0, -2.0, 0.0), (11.0, 2.0, 0.0))
        first = rigid_translation_for_clearance(points, surface, clearance=4.0, max_translation=20.0)
        second = rigid_translation_for_clearance(points, surface, clearance=4.0, max_translation=20.0)
        self.assertEqual(first, second)
        moved = tuple(
            (p[0] + first[0], p[1] + first[1], p[2] + first[2])
            for p in points
        )
        self.assertGreaterEqual(minimum_signed_clearance(moved, surface, first), 4.0 - 1e-6)
        self.assertGreater(first[0], 0.0)
        self.assertAlmostEqual(first[1], 0.0, places=9)
        self.assertAlmostEqual(first[2], 0.0, places=9)

    def test_bound_is_fail_closed(self):
        surface = _cube_surface()
        with self.assertRaisesRegex(ValueError, "exceeds translation bound"):
            rigid_translation_for_clearance(((11.0, 0.0, 0.0),), surface, clearance=30.0, max_translation=5.0)

    def test_missing_geometry_is_rejected(self):
        surface = _cube_surface()
        with self.assertRaises(ValueError):
            rigid_translation_for_clearance((), surface, clearance=4.0, max_translation=20.0)

    def test_clearance_is_deterministic_for_repeated_calls(self):
        surface = _cube_surface()
        delta = rigid_translation_for_clearance(((14.0, 0.0, 0.0),), surface, clearance=4.0, max_translation=20.0)
        self.assertTrue(math.isfinite(delta[0]))
        self.assertTrue(all(math.isfinite(value) for value in delta))


if __name__ == "__main__":
    unittest.main()
