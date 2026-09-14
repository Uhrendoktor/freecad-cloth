import json
import tempfile
import unittest
from pathlib import Path

from freecad_cloth.avatar.HierarchicalPose import build_hierarchical_avatar_mesh
from freecad_cloth.avatar.HumanoidMesh import (
    _bone_source_endpoints,
    _joint_point,
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
