import unittest

from freecad_cloth.avatar.AvatarCollision import surface_from_triangles
from freecad_cloth.avatar.TargetAwarePlacement import (
    TargetPlacementError,
    apply_rigid_delta,
    assert_minimum_surface_clearance,
    require_ready_target_status,
    solve_rigid_z,
    target_surface_anchor,
    wrap_normal,
)


def box_surface():
    vertices = (
        (-10, -10, -10), (10, -10, -10), (10, 10, -10), (-10, 10, -10),
        (-10, -10, 10), (10, -10, 10), (10, 10, 10), (-10, 10, 10),
    )
    triangles = (
        (0, 1, 2), (0, 2, 3),
        (5, 6, 4), (6, 7, 4),
        (0, 4, 5), (0, 5, 1),
        (1, 5, 6), (1, 6, 2),
        (2, 6, 7), (2, 7, 3),
        (3, 7, 4), (3, 4, 0),
    )
    return surface_from_triangles(vertices, triangles)


class TargetAwarePlacementTests(unittest.TestCase):
    def test_wrap_normals_match_canonical_axes(self):
        self.assertEqual(wrap_normal("front"), (0.0, 1.0, 0.0))
        self.assertEqual(wrap_normal("back"), (0.0, -1.0, 0.0))

    def test_target_surface_anchor_is_deterministic(self):
        surface = box_surface()
        first = target_surface_anchor(surface, (0, 0, 25), (0, 0, 1))
        second = target_surface_anchor(surface, (0, 0, 25), (0, 0, 1))
        self.assertEqual(first, second)
        self.assertAlmostEqual(first.point[2], 10.0, places=7)
        self.assertEqual(first.normal, (0.0, 0.0, 1.0))

    def test_adjacent_coplanar_triangles_are_not_ambiguous(self):
        surface = surface_from_triangles(
            ((-10,-10,0),(10,-10,0),(10,10,0),(-10,10,0)),
            ((0,1,2),(0,2,3)),
        )
        hit = target_surface_anchor(surface, (0,0,10), (0,0,1))
        self.assertAlmostEqual(hit.point[2], 0.0, places=7)

    def test_equal_distance_distinct_locations_fail_closed(self):
        surface = surface_from_triangles(
            ((-20,-20,0),(-10,-20,0),(-10,20,0),(-20,20,0),
             (10,-20,0),(20,-20,0),(20,20,0),(10,20,0)),
            ((0,1,2),(0,2,3),(4,5,6),(4,6,7)),
        )
        with self.assertRaises(TargetPlacementError):
            target_surface_anchor(surface, (0,0,10), (0,0,1))

    def test_rigid_solution_is_deterministic_and_bounded(self):
        source = ((-5, 0, 0), (5, 0, 0))
        target = ((-5, 20, 2), (5, 20, 2))
        delta = solve_rigid_z(source, target, max_translation=100, max_rotation=45)
        self.assertAlmostEqual(delta.rotation_z, 0.0, places=7)
        self.assertAlmostEqual(delta.translation[0], 0.0, places=7)
        self.assertAlmostEqual(delta.translation[1], 20.0, places=7)
        self.assertAlmostEqual(delta.translation[2], 2.0, places=7)
        result = apply_rigid_delta(source, delta)
        for actual, expected in zip(result, target):
            for a, b in zip(actual, expected):
                self.assertAlmostEqual(a, b, places=7)

    def test_rigid_transform_bound_fails_closed(self):
        with self.assertRaises(TargetPlacementError):
            solve_rigid_z(((0, 0, 0),), ((1000, 0, 0),), max_translation=100, max_rotation=45)

    def test_step_zero_clearance_is_enforced(self):
        surface = box_surface()
        self.assertAlmostEqual(assert_minimum_surface_clearance(surface, ((0, 0, 18),), 8.0), 8.0, places=7)
        with self.assertRaises(TargetPlacementError):
            assert_minimum_surface_clearance(surface, ((0, 0, 11),), 8.0)

    def test_non_ready_target_states_fail_closed(self):
        for status in (
            None,
            {"state": "missing", "message": "target missing"},
            {"state": "stale", "message": "target changed"},
            {"state": "disabled", "message": "target disabled"},
            {"state": "unbuilt", "message": "collision cache missing"},
        ):
            with self.assertRaises(TargetPlacementError):
                require_ready_target_status(status)


if __name__ == "__main__":
    unittest.main()
