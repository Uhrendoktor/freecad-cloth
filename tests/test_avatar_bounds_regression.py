import unittest

from freecad_cloth.avatar.AvatarModel import AvatarParameters, generate_mesh


class AvatarBoundsRegressionTests(unittest.TestCase):
    def test_generated_default_avatar_has_compact_plausible_bounds(self):
        vertices, triangles, _landmarks = generate_mesh(AvatarParameters(skin_offset=0))
        self.assertAlmostEqual(max(v[2] for v in vertices) - min(v[2] for v in vertices), 1750.0, places=6)
        self.assertLess(max(v[0] for v in vertices) - min(v[0] for v in vertices), 5000.0)
        self.assertLess(max(v[1] for v in vertices) - min(v[1] for v in vertices), 5000.0)
        used = {index for triangle in triangles for index in triangle}
        self.assertEqual(used, set(range(len(vertices))))


if __name__ == "__main__":
    unittest.main()
