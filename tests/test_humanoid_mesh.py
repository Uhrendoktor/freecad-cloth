import os
import tempfile
import unittest

from freecad_cloth.avatar.AvatarModel import AvatarParameters, Pose
from freecad_cloth.avatar.HumanoidMesh import (
    MAKEHUMAN_BASE_URL,
    MAKEHUMAN_BASE_SHA256,
    MeshData,
    _map_makehuman_axes,
    fit_makehuman_mesh,
    parse_obj,
)


class HumanoidMeshTests(unittest.TestCase):
    def test_obj_parser_keeps_largest_connected_surface_and_triangulates(self):
        data = parse_obj("""
        # connected body surface: two triangles
        v 0 0 0
        v 1 0 0
        v 0 1 0
        v 1 1 0
        v 20 20 20
        v 21 20 20
        v 20 21 20
        f 1 2 3
        f 2 4 3
        # disconnected helper triangle
        f 5 6 7
        """)
        self.assertEqual(len(data.vertices), 4)
        self.assertEqual(len(data.triangles), 2)
        self.assertTrue(all(max(tri) < 4 for tri in data.triangles))

    def test_obj_parser_triangulates_faces_and_supports_negative_indices(self):
        data = parse_obj("""
        v 0 0 0
        v 1 0 0
        v 1 1 0
        v 0 1 0
        f 1 2 3 4
        f -4 -2 -1
        """)
        self.assertEqual(data.triangles, ((0, 1, 2), (0, 2, 3), (0, 2, 3)))

    def test_mesh_data_rejects_invalid_indices(self):
        with self.assertRaises(Exception):
            MeshData(((0.0, 0.0, 0.0),) * 3, ((0, 1, 3),)).validate()

    def test_real_source_is_pinned(self):
        self.assertIn(MAKEHUMAN_BASE_SHA256, "8e761e6624b8f54536409135d1636da63b32486a90d4897f84e121d144f6fb4c")
        self.assertIn("1f508f6083b2f823dab15de924b3bde72e08d77c", MAKEHUMAN_BASE_URL)
        self.assertTrue(MAKEHUMAN_BASE_URL.endswith("/makehuman/data/3dobjs/base.obj"))

    def test_makehuman_axis_map_is_upright_and_right_handed(self):
        mapped = _map_makehuman_axes(((-2.0, -5.0, -1.0), (2.0, 5.0, 1.0)))
        self.assertEqual(mapped[0], (-2.0, 1.0, 0.0))
        self.assertEqual(mapped[1], (2.0, -1.0, 1.0))

    def test_fit_preserves_topology_and_applies_height_and_skin_offset(self):
        source = MeshData(
            (
                (-1.0, -1.0, -1.0), (1.0, -1.0, -1.0),
                (1.0, 1.0, -1.0), (-1.0, 1.0, -1.0),
                (-1.0, -1.0, 1.0), (1.0, -1.0, 1.0),
                (1.0, 1.0, 1.0), (-1.0, 1.0, 1.0),
            ),
            (
                (0, 1, 2), (0, 2, 3), (4, 7, 6), (4, 6, 5),
                (0, 4, 5), (0, 5, 1), (1, 5, 6), (1, 6, 2),
                (2, 6, 7), (2, 7, 3), (4, 0, 3), (4, 3, 7),
            ),
        )
        base = AvatarParameters(skin_offset=0)
        padded = AvatarParameters(skin_offset=8)
        fitted = fit_makehuman_mesh(source, base)
        fitted_padded = fit_makehuman_mesh(source, padded)
        self.assertEqual(fitted.triangles, source.triangles)
        self.assertEqual(len(fitted.vertices), len(source.vertices))
        self.assertAlmostEqual(max(v[2] for v in fitted.vertices), 1750.0)
        self.assertNotEqual(fitted.vertices, fitted_padded.vertices)

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

    def test_explicit_local_source_does_not_require_network(self):
        from freecad_cloth.avatar.HumanoidMesh import load_makehuman_mesh
        fd, path = tempfile.mkstemp(prefix="cloth-humanoid-", suffix=".obj")
        os.close(fd)
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n")
            loaded = load_makehuman_mesh(path)
            self.assertEqual(len(loaded.vertices), 3)
            self.assertEqual(loaded.triangles, ((0, 1, 2),))
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
