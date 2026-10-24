# Copyright (C) 2026 FreeCAD Cloth contributors
import json
import unittest

from freecad_cloth.avatar.AvatarModel import AvatarParameters, Pose, generate_mesh
from freecad_cloth.avatar.HierarchicalPose import build_hierarchical_avatar_mesh


class AvatarStandingPoseTests(unittest.TestCase):
    def test_presets_have_explicit_arm_defaults_without_sentinels(self):
        self.assertEqual((Pose().left_arm_angle, Pose().right_arm_angle), (70.0, 70.0))
        self.assertEqual(
            (Pose("sewing").left_arm_angle, Pose("sewing").right_arm_angle), (55.0, 55.0)
        )
        self.assertEqual(
            (Pose("sitting").left_arm_angle, Pose("sitting").right_arm_angle), (25.0, 25.0)
        )
        self.assertEqual(Pose("standing", 12.0, 12.0).left_arm_angle, 12.0)

    def test_unsupported_avatar_schema_versions_are_rejected(self):
        """Reject obsolete and unknown schemas instead of maintaining a migration path."""
        template = {
            "schema_version": 4,
            "units": "mm",
            "measurements": {},
            "skin_offset": 0,
            "pose": {"preset": "standing"},
        }
        for schema_version in (1, 2, 3, 5):
            payload = json.dumps({**template, "schema_version": schema_version})
            with self.subTest(schema_version=schema_version), self.assertRaisesRegex(
                ValueError, "unsupported avatar schema version"
            ):
                AvatarParameters.from_json(payload)

    def test_generator_and_builder_share_the_same_fk_mesh(self):
        params = AvatarParameters()
        vertices, triangles, _landmarks = generate_mesh(params)
        built = build_hierarchical_avatar_mesh(params)
        self.assertEqual(vertices, built.vertices)
        self.assertEqual(triangles, built.triangles)

    def test_near_horizontal_arm_angle_extends_the_mesh_laterally(self):
        horizontal = AvatarParameters(pose=Pose("standing", 12.0, 12.0))
        lowered = AvatarParameters(pose=Pose("standing", 70.0, 70.0))

        def x_bounds(parameters):
            vertices, _triangles, _landmarks = generate_mesh(parameters)
            xs = tuple(float(point[0]) for point in vertices)
            return min(xs), max(xs)

        horizontal_bounds = x_bounds(horizontal)
        lowered_bounds = x_bounds(lowered)

        # A 12-degree arm should be much closer to horizontal than the 70-degree
        # standing preset. Assert against the emitted mesh, not only its landmarks.
        self.assertLess(horizontal_bounds[0], lowered_bounds[0] - 100.0)
        self.assertGreater(horizontal_bounds[1], lowered_bounds[1] + 100.0)

    def test_default_fk_raises_arms_and_preserves_bilateral_symmetry(self):
        params = AvatarParameters()
        actual_vertices, _triangles, _landmarks = generate_mesh(params)
        reference_vertices, _triangles, _landmarks = generate_mesh(
            AvatarParameters(pose=Pose("t_pose"))
        )

        def bounds(vertices):
            return tuple(
                (min(point[axis] for point in vertices), max(point[axis] for point in vertices))
                for axis in range(3)
            )

        actual, expected = bounds(actual_vertices), bounds(reference_vertices)

        # Compare like-for-like Anny geometry: the 12-degree reference is
        # near-horizontal, while the default 70-degree standing pose lowers
        # both arms inward.
        self.assertGreater(actual[0][0], expected[0][0] + 50.0)
        self.assertLess(actual[0][1], expected[0][1] - 50.0)
        self.assertAlmostEqual(actual[0][0], -actual[0][1], delta=2.0)

        # Arm rotation is in the sagittal plane; depth must remain unchanged.
        for actual_depth, expected_depth in zip(actual[1], expected[1], strict=True):
            self.assertAlmostEqual(actual_depth, expected_depth, delta=2.0)


if __name__ == "__main__":
    unittest.main()
