import unittest

from freecad_cloth.avatar.AvatarVisualSanity import AvatarVisualSanityError, inspect_avatar_mesh


class AvatarVisualSanityTests(unittest.TestCase):
    def test_accepts_sane_humanoid_bounds(self):
        vertices = ((-100, -50, 0), (100, 50, 1750), (-110, 45, 800), (110, -45, 800))
        triangles = ((0, 1, 2), (0, 2, 3))
        result = inspect_avatar_mesh(vertices, triangles, expected_height=1750)
        self.assertEqual(result.height, 1750.0)
        self.assertEqual(result.triangle_count, 2)
        self.assertLess(result.lateral_height_ratio, 0.2)

    def test_accepts_sane_humanoid_even_when_depth_exceeds_width(self):
        vertices = ((-150, -260, 0), (150, 260, 1750), (-120, 250, 900), (120, -250, 900))
        triangles = ((0, 1, 2), (0, 2, 3))
        result = inspect_avatar_mesh(vertices, triangles, expected_height=1750)
        self.assertEqual(result.height, 1750.0)
        self.assertEqual(result.width, 520.0)
        self.assertEqual(result.depth, 300.0)

    def test_rejects_empty_mesh(self):
        with self.assertRaises(AvatarVisualSanityError):
            inspect_avatar_mesh((), ())

    def test_rejects_invalid_triangle_indices(self):
        with self.assertRaises(AvatarVisualSanityError):
            inspect_avatar_mesh(((0, 0, 0), (1, 0, 0), (0, 1, 1)), ((0, 1, 3),))

    def test_rejects_unrealistically_wide_avatar(self):
        vertices = ((-900, -100, 0), (900, 100, 1750), (-850, 50, 900), (850, -50, 900))
        triangles = ((0, 1, 2), (0, 2, 3))
        with self.assertRaises(AvatarVisualSanityError):
            inspect_avatar_mesh(vertices, triangles, expected_height=1750)

    def test_rejects_large_depth_without_treating_it_as_height(self):
        vertices = ((-100, -900, 0), (100, 900, 1750), (-110, 850, 900), (110, -850, 900))
        triangles = ((0, 1, 2), (0, 2, 3))
        with self.assertRaises(AvatarVisualSanityError):
            inspect_avatar_mesh(vertices, triangles, expected_height=1750)

    def test_rejects_wrong_height(self):
        vertices = ((-100, -50, 0), (100, 50, 1700), (-110, 45, 800), (110, -45, 800))
        triangles = ((0, 1, 2), (0, 2, 3))
        with self.assertRaises(AvatarVisualSanityError):
            inspect_avatar_mesh(vertices, triangles, expected_height=1750)


if __name__ == "__main__":
    unittest.main()



def test_arrangement_point_parser_shared_with_simulation_layer():
    from freecad_cloth.shared.ArrangementPointRecord import parse_arrangement_point_record
    from freecad_cloth.avatar.AvatarFitting import ArrangementPoint

    legacy = "shoulder_right|220,0,1347"
    extended = "shoulder_left|-220,0,1347|back|12.5|shoulder"
    assert parse_arrangement_point_record(legacy) == (
        "shoulder_right", (220.0, 0.0, 1347.0), "front", 0.0, ""
    )
    assert ArrangementPoint.from_string(legacy).position() == (220.0, 0.0, 1347.0)
    assert ArrangementPoint.from_string(extended).to_string() == extended


def test_arrangement_point_parser_rejects_malformed_or_non_finite_records():
    import pytest
    from freecad_cloth.shared.ArrangementPointRecord import parse_arrangement_point_record

    for record in ("", "shoulder|1,2", "shoulder|1,2,3|front", "shoulder|nan,2,3"):
        with pytest.raises(ValueError):
            parse_arrangement_point_record(record)
