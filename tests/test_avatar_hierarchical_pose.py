import json
import tempfile
import unittest
from pathlib import Path

from freecad_cloth.avatar.HierarchicalPose import build_hierarchical_avatar_mesh
from freecad_cloth.avatar.HumanoidMesh import (
    _bone_source_endpoints,
    _joint_point,
    _map_arm_weights_to_physical_sides,
    _rotate_xz,
    load_makehuman_skeleton,
)
from freecad_cloth.avatar.AvatarModel import AvatarParameters


class AvatarHierarchicalPoseTests(unittest.TestCase):
    def test_joint_point_uses_authored_vertex_indices(self):
        vertices = ((0.0, 0.0, 0.0), (2.0, 4.0, 6.0))
        self.assertEqual(_joint_point(vertices, [0, 1]), (1.0, 2.0, 3.0))

    def test_bone_endpoints_follow_authored_skeleton(self):
        vertices = ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (20.0, 0.0, 0.0))
        skeleton = {
            "bones": {"upperarm01.L": {"head": "h", "tail": "t"}},
            "joints": {"h": [0], "t": [1]},
        }
        self.assertEqual(_bone_source_endpoints(vertices, skeleton, "upperarm01.L"), ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0)))

    def test_arm_weight_labels_are_mapped_to_physical_x_sides(self):
        vertices = ((-100.0, 0.0, 0.0), (100.0, 0.0, 0.0))
        mapped = _map_arm_weights_to_physical_sides(vertices, ((0.0, 1.0), (1.0, 0.0)))
        self.assertEqual(mapped, ((1.0, 0.0), (0.0, 1.0)))

    def test_rigid_arm_rotation_preserves_distance_to_authored_pivot(self):
        point = (300.0, 0.0, 1300.0)
        pivot = (170.0, 0.0)
        rotated = _rotate_xz(point, pivot, 0.7)
        before = ((point[0] - pivot[0]) ** 2 + (point[2] - pivot[1]) ** 2) ** 0.5
        after = ((rotated[0] - pivot[0]) ** 2 + (rotated[2] - pivot[1]) ** 2) ** 0.5
        self.assertAlmostEqual(before, after, places=6)

    def test_pinned_makehuman_skeleton_has_wrist_child_of_forearm(self):
        skeleton = load_makehuman_skeleton()
        self.assertEqual(skeleton["bones"]["wrist.L"]["parent"], "lowerarm02.L")
        self.assertEqual(skeleton["bones"]["wrist.R"]["parent"], "lowerarm02.R")

    def test_hierarchical_builder_uses_real_mesh_provider(self):
        mesh = build_hierarchical_avatar_mesh(AvatarParameters(skin_offset=0))
        self.assertEqual(len(mesh.vertices), 13380)
        self.assertTrue(mesh.triangles)

    def test_weight_fixture_is_structurally_authored(self):
        payload = {"weights": {"upperarm01.L": [[0, 0.4]], "wrist.L": [[1, 0.6]], "finger2-1.L": [[1, 0.2]]}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "weights.mhw"
            path.write_text(json.dumps(payload), encoding="utf-8")
            from freecad_cloth.avatar.HumanoidMesh import load_makehuman_arm_weights
            left, right = load_makehuman_arm_weights(2, str(path))
        self.assertAlmostEqual(left[0], 0.4)
        self.assertAlmostEqual(left[1], 0.8)
        self.assertEqual(right, (0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
