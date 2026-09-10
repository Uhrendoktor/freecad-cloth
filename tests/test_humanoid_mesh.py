import os
import tempfile
import unittest

from freecad_cloth.avatar.AvatarModel import AvatarParameters
from freecad_cloth.avatar.HumanoidMesh import (
    MAKEHUMAN_BASE_URL,
    MAKEHUMAN_BASE_SHA256,
    MeshData,
    fit_makehuman_mesh,
    parse_obj,
)


class HumanoidMeshTests(unittest.TestCase):
    def test_obj_parser_triangulates_faces_and_supports_negative_indices(self):
        data = parse_obj("""
        # quad + negative-index triangle
        v 0 0 0
        v 1 0 0
        v 1 1 0
        v 0 1 0
        f 1 2 3 4
        f -4 -2 -1
        """)
        self.assertEqual(data.vertices, ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)))
        self.assertEqual(data.triangles, ((0, 1, 2), (0, 2, 3), (0, 2, 3)))

    def test_mesh_data_rejects_invalid_indices(self):
        with self.assertRaises(Exception):
            MeshData(((0.0, 0.0, 0.0),) * 3, ((0, 1, 3),)).validate()

    def test_real_source_is_pinned(self):
        self.assertIn(MAKEHUMAN_BASE_SHA256, "8e761e6624b8f54536409135d1636da63b32486a90d4897f84e121d144f6fb4c")
        self.assertIn("1f508f6083b2f823dab15de924b3bde72e08d77c9", MAKEHUMAN_BASE_URL)
        self.assertTrue(MAKEHUMAN_BASE_URL.endswith("/makehuman/data/3dobjs/base.obj"))

    def test_fit_uses_source_z_as_anatomical_height(self):
        source = parse_obj("""
        v -1 -0.5 0
        v 1 -0.5 0
        v 1 0.5 0
        v -1 0.5 0
        v -1 -0.5 10
        v 1 -0.5 10
        v 1 0.5 10
        v -1 0.5 10
        f 1 2 3 4
        f 5 8 7 6
        f 1 5 6 2
        f 2 6 7 3
        f 3 7 8 4
        f 4 8 5 1
        """)
        fitted = fit_makehuman_mesh(source, AvatarParameters(skin_offset=0))
        self.assertAlmostEqual(min(v[2] for v in fitted.vertices), 0.0)
        self.assertAlmostEqual(max(v[2] for v in fitted.vertices), 1750.0)
        self.assertAlmostEqual(max(v[1] for v in fitted.vertices) - min(v[1] for v in fitted.vertices), 350.0)

    def test_fit_preserves_topology_and_applies_height_and_skin_offset(self):
        source = parse_obj("""
        v -1 0 -1
        v 1 0 -1
        v 1 1 -1
        v -1 1 -1
        v -1 0 1
        v 1 0 1
        v 1 1 1
        v -1 1 1
        f 1 2 3 4
        f 5 8 7 6
        f 1 5 6 2
        f 2 6 7 3
        f 3 7 8 4
        f 4 8 5 1
        """)
        base = AvatarParameters(skin_offset=0)
        padded = AvatarParameters(skin_offset=8)
        fitted = fit_makehuman_mesh(source, base)
        fitted_padded = fit_makehuman_mesh(source, padded)
        self.assertEqual(fitted.triangles, source.triangles)
        self.assertEqual(len(fitted.vertices), len(source.vertices))
        self.assertAlmostEqual(max(v[2] for v in fitted.vertices), 1750.0)
        self.assertNotEqual(fitted.vertices, fitted_padded.vertices)

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
