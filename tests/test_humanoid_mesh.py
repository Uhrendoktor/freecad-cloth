import unittest

from freecad_cloth.avatar.AvatarModel import AvatarParameters
from freecad_cloth.avatar.HumanoidMesh import _map_makehuman_axes, fit_makehuman_mesh, parse_obj


class HumanoidMeshTests(unittest.TestCase):
    def test_parser_keeps_largest_connected_surface(self):
        obj = """
# body component: two connected triangles
v 0 0 0
v 1 0 0
v 0 1 0
v 0 0 1
v 1 1 0
f 1 2 3
f 2 5 3
# disconnected helper triangle
v 20 20 20
v 21 20 20
v 20 21 20
f 6 7 8
"""
        mesh = parse_obj(obj)
        self.assertEqual(len(mesh.vertices), 5)
        self.assertEqual(len(mesh.triangles), 2)
        self.assertTrue(all(max(tri) < 5 for tri in mesh.triangles))

    def test_makehuman_axis_map_is_upright_and_right_handed(self):
        vertices = ((-2.0, -5.0, -1.0), (2.0, 5.0, 1.0))
        mapped = _map_makehuman_axes(vertices)
        self.assertEqual(mapped[0], (-2.0, 1.0, 0.0))
        self.assertEqual(mapped[1], (2.0, -1.0, 1.0))

    def test_fit_preserves_standing_aspect_ratio(self):
        params = AvatarParameters()
        vertices = (
            (-0.3, 0.0, -0.15), (0.3, 0.0, -0.15),
            (-0.25, 8.0, -0.15), (0.25, 8.0, -0.15),
            (-0.3, 0.0, 0.15), (0.3, 0.0, 0.15),
            (-0.25, 8.0, 0.15), (0.25, 8.0, 0.15),
        )
        triangles = (
            (0, 1, 2), (1, 3, 2), (4, 6, 5), (5, 6, 7),
            (0, 4, 1), (1, 4, 5), (2, 3, 6), (3, 7, 6),
            (0, 2, 4), (2, 6, 4), (1, 5, 3), (3, 5, 7),
        )
        fitted = fit_makehuman_mesh(type("Mesh", (), {"vertices": vertices, "triangles": triangles, "validate": lambda self: self})(), params)
        xs = [p[0] for p in fitted.vertices]
        zs = [p[2] for p in fitted.vertices]
        self.assertAlmostEqual(min(zs), 0.0, places=6)
        self.assertAlmostEqual(max(zs), 1750.0, places=6)
        self.assertGreater(max(zs) - min(zs), 5.0 * (max(xs) - min(xs)))


if __name__ == "__main__":
    unittest.main()
