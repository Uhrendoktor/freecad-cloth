import json
import unittest

from freecad_cloth.avatar.AvatarModel import AvatarParameters, Pose, generate_mesh
from freecad_cloth.avatar.HierarchicalPose import build_hierarchical_avatar_mesh
from freecad_cloth.avatar.HumanoidMesh import fit_makehuman_mesh, load_makehuman_arm_weights, load_makehuman_mesh


class AvatarStandingPoseTests(unittest.TestCase):
    def test_presets_have_explicit_arm_defaults_without_sentinels(self):
        self.assertEqual((Pose().left_arm_angle, Pose().right_arm_angle), (70.0, 70.0))
        self.assertEqual((Pose("sewing").left_arm_angle, Pose("sewing").right_arm_angle), (55.0, 55.0))
        self.assertEqual((Pose("sitting").left_arm_angle, Pose("sitting").right_arm_angle), (25.0, 25.0))
        self.assertEqual(Pose("standing", 12.0, 12.0).left_arm_angle, 12.0)

    def test_schema_one_sentinels_are_migrated_at_load(self):
        legacy = {
            "schema_version": 1,
            "units": "mm",
            "measurements": {},
            "skin_offset": 0,
            "pose": {"preset": "standing", "left_arm_angle": 12, "right_arm_angle": 12},
        }
        migrated = AvatarParameters.from_json(json.dumps(legacy))
        self.assertEqual(migrated.schema_version, 2)
        self.assertEqual((migrated.pose.left_arm_angle, migrated.pose.right_arm_angle), (70.0, 70.0))

        legacy["pose"]["preset"] = "sewing"
        migrated = AvatarParameters.from_json(json.dumps(legacy))
        self.assertEqual((migrated.pose.left_arm_angle, migrated.pose.right_arm_angle), (55.0, 55.0))

    def test_generator_and_builder_share_the_same_fk_mesh(self):
        params = AvatarParameters()
        vertices, triangles, _landmarks = generate_mesh(params)
        built = build_hierarchical_avatar_mesh(params)
        self.assertEqual(vertices, built.vertices)
        self.assertEqual(triangles, built.triangles)

    def test_default_fk_raises_arms_and_preserves_bilateral_symmetry(self):
        params = AvatarParameters()
        actual_vertices, _triangles, _landmarks = generate_mesh(params)
        reference = fit_makehuman_mesh(
            load_makehuman_mesh(),
            params,
            arm_weights=load_makehuman_arm_weights(13380),
        ).vertices

        def bounds(vertices):
            return tuple(
                (min(point[axis] for point in vertices), max(point[axis] for point in vertices))
                for axis in range(3)
            )

        actual, expected = bounds(actual_vertices), bounds(reference)

        # The 70-degree standing preset deliberately widens the mannequin's
        # X envelope; comparing it to the unposed reference envelope is stale.
        self.assertLess(actual[0][0], expected[0][0] - 50.0)
        self.assertGreater(actual[0][1], expected[0][1] + 50.0)
        self.assertAlmostEqual(actual[0][0], -actual[0][1], delta=2.0)

        # Arm rotation is in the sagittal plane; depth must remain unchanged.
        for actual_depth, expected_depth in zip(actual[1], expected[1]):
            self.assertAlmostEqual(actual_depth, expected_depth, delta=2.0)


if __name__ == "__main__":
    unittest.main()
