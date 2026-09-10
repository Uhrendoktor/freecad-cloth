"""Regression tests for the production avatar fitting path."""
import unittest

from freecad_cloth.avatar.HumanoidMesh import (
    MAKEHUMAN_BODY_VERTEX_COUNT,
    MeshData,
    AvatarParameters,
    Pose,
    fit_makehuman_mesh,
    generate_mesh,
    parse_obj,
    DEFAULT_MEASUREMENTS,
)


class AvatarFittingTests(unittest.TestCase):
    def test_obj_parser_excludes_hm08_helper_faces(self):
        lines = ["v 0 0 0"] * MAKEHUMAN_BODY_VERTEX_COUNT
        lines[1] = "v 1 0 0"
        lines[2] = "v 0 1 0"
        lines.append("v 10 0 0")
        lines.extend(("f 1 2 3", "f 1 2 %d" % (MAKEHUMAN_BODY_VERTEX_COUNT + 1)))
        mesh = parse_obj("\n".join(lines))
        self.assertEqual(len(mesh.vertices), MAKEHUMAN_BODY_VERTEX_COUNT)
        self.assertEqual(mesh.triangles, ((0, 1, 2),))

    def test_default_mannequin_preserves_source_shape_after_height_normalization(self):
        source = MeshData(
            ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 1.0, 1.0)),
            ((0, 1, 2), (1, 3, 2), (0, 2, 3)),
        )
        params = AvatarParameters(pose=Pose("standing", 0.0, 0.0))
        fitted = fit_makehuman_mesh(source, params)
        self.assertEqual(fitted.triangles, source.triangles)
        self.assertEqual(fitted.vertices, ((0.0, 0.0, 0.0), (1750.0, 0.0, 0.0), (0.0, 1750.0, 0.0), (0.0, 1750.0, 1750.0)))

    def test_mannequin_is_deterministic_and_landmarked(self):
        params = AvatarParameters()
        first = generate_mesh(params)
        second = generate_mesh(params)
        self.assertEqual(first, second)
        self.assertGreater(len(first[0]), 100)
        self.assertGreater(len(first[1]), 100)
        self.assertGreaterEqual({p.name for p in first[2]}, {"neck", "chest", "waist", "hip", "shoulder_left", "shoulder_right"})

    def test_mannequin_measurement_change_is_parametric(self):
        params = AvatarParameters()
        wider = params.with_measurements(chest=params.measurement("chest") + 100)
        self.assertEqual(params.measurement("chest"), DEFAULT_MEASUREMENTS["chest"])
        self.assertNotEqual(generate_mesh(params)[0], generate_mesh(wider)[0])

    def test_fit_uses_source_z_as_anatomical_height(self):
        source = MeshData(
            ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 10.0), (1.0, 1.0, 10.0)),
            ((0, 1, 2), (1, 3, 2)),
        )
        fitted = fit_makehuman_mesh(source, AvatarParameters(pose=Pose("standing", 0.0, 0.0)))
        z_values = [vertex[2] for vertex in fitted.vertices]
        y_values = [vertex[1] for vertex in fitted.vertices]
        self.assertEqual(max(z_values) - min(z_values), 1750.0)
        self.assertEqual(max(y_values) - min(y_values), 350.0)


if __name__ == "__main__":
    unittest.main()
