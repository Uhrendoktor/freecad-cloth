import json
import os
import tempfile
import unittest
from pathlib import Path

from freecad_cloth.avatar.AvatarModel import AvatarParameters
from freecad_cloth.avatar.HumanoidMesh import (
    MAKEHUMAN_BASE_SHA256,
    MAKEHUMAN_BASE_URL,
    MAKEHUMAN_SKELETON_SIZE,
    MAKEHUMAN_WEIGHTS_SIZE,
    HumanoidMeshError,
    MeshData,
    _load_source_vertices,
    _map_makehuman_axes,
    _reoriented_triangles,
    _verified_skeleton,
    _verified_weights,
    fit_makehuman_mesh,
    load_makehuman_mesh,
    load_makehuman_skeleton,
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
        self.assertEqual(
            data.vertices, ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0))
        )
        self.assertEqual(data.triangles, ((0, 1, 2), (0, 2, 3), (0, 2, 3)))

    def test_mesh_data_rejects_invalid_indices(self):
        with self.assertRaises(HumanoidMeshError):
            MeshData(((0.0, 0.0, 0.0),) * 3, ((0, 1, 3),)).validate()

    @staticmethod
    def _write_sized_json(path: Path, payload: object, size: int) -> None:
        encoded = json.dumps(payload, separators=(",", ":"))
        if len(encoded) > size:
            raise AssertionError("test JSON payload is larger than the expected cache size")
        path.write_text(encoded + " " * (size - len(encoded)), encoding="utf-8")

    def test_mesh_data_rejects_non_finite_vertex_coordinates(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                mesh = MeshData(
                    ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, value, 1.0)),
                    ((0, 1, 2),),
                )
                with self.assertRaisesRegex(HumanoidMeshError, "invalid vertex coordinates"):
                    mesh.validate()

    def test_source_vertex_loader_rejects_non_finite_coordinates(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "malformed.obj"
            path.write_text(
                "v 0 0 0\\nv 1 0 0\\nv nan 1 0\\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(HumanoidMeshError, "finite"):
                _load_source_vertices(str(path))

    def test_obj_parser_rejects_non_finite_vertex_coordinates(self):
        for value in ("nan", "inf", "-inf"):
            with self.subTest(value=value):
                source = f"v 0 0 0\nv 1 0 0\nv {value} 1 0\nf 1 2 3\n"
                with self.assertRaisesRegex(HumanoidMeshError, "invalid vertex coordinates"):
                    parse_obj(source)

    def test_mesh_data_rejects_non_integer_face_indices(self):
        mesh = MeshData(
            ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
            ((0.5, 1, 2),),
        )
        with self.assertRaisesRegex(HumanoidMeshError, "invalid face"):
            mesh.validate()

    def test_weights_cache_verifier_rejects_malformed_or_empty_payloads(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "weights.mhw"
            for payload in ([], {"weights": {}}):
                with self.subTest(payload_type=type(payload).__name__):
                    self._write_sized_json(path, payload, MAKEHUMAN_WEIGHTS_SIZE)
                    self.assertFalse(_verified_weights(path))

    def test_skeleton_loader_rejects_malformed_explicit_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "skeleton.mhskel"
            path.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(HumanoidMeshError, "invalid bones or joints"):
                load_makehuman_skeleton(str(path))

    def test_skeleton_cache_verifier_rejects_malformed_or_empty_payloads(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "skeleton.mhskel"
            payloads = (
                [],
                {"bones": {}, "joints": {}},
                {"bones": {"spine": {"head": "missing", "tail": "missing"}}, "joints": {}},
                {
                    "bones": {"spine": {"head": "head", "tail": "tail"}},
                    "joints": {"head": [], "tail": [0]},
                },
            )
            for payload in payloads:
                with self.subTest(payload_type=type(payload).__name__, size=len(str(payload))):
                    self._write_sized_json(path, payload, MAKEHUMAN_SKELETON_SIZE)
                    self.assertFalse(_verified_skeleton(path))

    def test_real_source_is_pinned(self):
        self.assertIn(
            MAKEHUMAN_BASE_SHA256,
            "8e761e6624b8f54536409135d1636da63b32486a90d4897f84e121d144f6fb4c",
        )
        self.assertIn("1f508f6083b2f823dab15de924b3bde72e08d77c9", MAKEHUMAN_BASE_URL)
        self.assertTrue(MAKEHUMAN_BASE_URL.endswith("/makehuman/data/3dobjs/base.obj"))

    def test_real_source_height_axis_is_makehuman_y_up_and_fits_to_z(self):
        source = load_makehuman_mesh()
        spans = tuple(
            max(vertex[axis] for vertex in source.vertices)
            - min(vertex[axis] for vertex in source.vertices)
            for axis in range(3)
        )
        fitted = fit_makehuman_mesh(source, AvatarParameters(skin_offset=0))
        fitted_spans = tuple(
            max(vertex[axis] for vertex in fitted.vertices)
            - min(vertex[axis] for vertex in fitted.vertices)
            for axis in range(3)
        )
        print(f"HM08_ORIENTATION source_spans={spans} fitted_spans={fitted_spans}", flush=True)
        self.assertGreater(spans[1], spans[0] * 1.5)
        self.assertGreater(spans[1], spans[2] * 2.0)
        self.assertAlmostEqual(fitted_spans[2], 1750.0, places=6)

    def test_map_preserves_z_up_orientation_and_normalizes_height(self):
        source = ((-2.0, 3.0, 5.0), (2.0, -3.0, 15.0))
        mapped = _map_makehuman_axes(source)
        self.assertEqual(mapped[0], (-2.0, 5.0, 1.0))
        self.assertEqual(mapped[1], (2.0, 15.0, 0.0))

    def test_axis_conversion_reverses_triangle_winding(self):
        self.assertEqual(_reoriented_triangles(((0, 1, 2), (2, 3, 0))), ((0, 2, 1), (2, 0, 3)))

    def test_fit_preserves_z_up_makehuman_orientation(self):
        source = parse_obj("""
        v -1 -0.5 0
        v 1 -0.5 0
        v 1 0.5 10
        v -1 0.5 10
        v -1 -0.5 5
        v 1 -0.5 5
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
        self.assertAlmostEqual(
            max(v[0] for v in fitted.vertices) - min(v[0] for v in fitted.vertices), 905.0
        )
        self.assertEqual(fitted.triangles, _reoriented_triangles(source.triangles))

    def test_fit_preserves_topology_and_applies_height_and_skin_offset(self):
        source = parse_obj("""
        v -1 -1 -1
        v 1 -1 -1
        v 1 1 -1
        v -1 1 -1
        v -1 -1 1
        v 1 -1 1
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
        self.assertEqual(fitted.triangles, _reoriented_triangles(source.triangles))
        self.assertEqual(len(fitted.vertices), len(source.vertices))
        self.assertAlmostEqual(max(v[2] for v in fitted.vertices), 1750.0)
        self.assertNotEqual(fitted.vertices, fitted_padded.vertices)

    def test_explicit_local_source_does_not_require_network(self):
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
