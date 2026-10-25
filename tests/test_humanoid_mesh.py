# Copyright (C) 2026 FreeCAD Cloth contributors
import json
import os
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path

import numpy as np
import trimesh
from pydantic import ValidationError

from freecad_cloth.avatar.AvatarModel import AvatarParameters
from freecad_cloth.avatar.HumanoidMesh import (
    MAKEHUMAN_BASE_SHA256,
    MAKEHUMAN_BASE_URL,
    MAKEHUMAN_DATA_ENV,
    MAKEHUMAN_SKELETON_SIZE,
    MAKEHUMAN_WEIGHTS_SIZE,
    HumanoidMeshError,
    MeshData,
    _find_local_base_mesh,
    _load_source_vertices,
    _make_source_fitted_mapper,
    _map_makehuman_axes,
    _reoriented_triangles,
    _section_circumference,
    _verified_skeleton,
    _verified_weights,
    ensure_makehuman_base,
    fit_makehuman_mesh,
    load_makehuman_mesh,
    load_makehuman_skeleton,
    parse_obj,
)
from freecad_cloth.avatar.MeshSanity import compact_mesh
from tests.support.assertions import require
from tests.support.closed_mesh_fixtures import CUBE_TRIANGLES


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
            msg = "test JSON payload is larger than the expected cache size"
            raise AssertionError(msg)
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
                "v 0 0 0\nv 1 0 0\nv nan 1 0\n",
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
        with self.assertRaises(ValidationError):
            MeshData(
                ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
                ((0.5, 1, 2),),
            )

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

    def test_local_mesh_discovery_accepts_only_verified_install_mesh(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            install = Path(directory) / "makehuman"
            mesh_path = install / "data" / "3dobjs" / "base.obj"
            mesh_path.parent.mkdir(parents=True)
            mesh_path.write_text("fixture", encoding="utf-8")

            environment = {MAKEHUMAN_DATA_ENV: str(install)}

            def verifier(candidate: Path) -> bool:
                return candidate == mesh_path

            self.assertEqual(
                _find_local_base_mesh(environ=environment, verifier=verifier), mesh_path
            )

    def test_local_mesh_discovery_ignores_unverified_install_mesh(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            install = Path(directory) / "makehuman"
            mesh_path = install / "data" / "3dobjs" / "base.obj"
            mesh_path.parent.mkdir(parents=True)
            mesh_path.write_text("different revision", encoding="utf-8")

            self.assertIsNone(
                _find_local_base_mesh(
                    environ={MAKEHUMAN_DATA_ENV: str(install)}, verifier=lambda _path: False
                )
            )

    def test_local_mesh_discovery_avoids_download(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            install = Path(directory) / "makehuman"
            mesh_path = install / "data" / "3dobjs" / "base.obj"
            mesh_path.parent.mkdir(parents=True)
            mesh_path.write_text("fixture", encoding="utf-8")
            cache = Path(directory) / "cache"
            environment = {
                MAKEHUMAN_DATA_ENV: str(install),
                "FREECAD_CLOTH_AVATAR_MESH": "",
                "FREECAD_CLOTH_AVATAR_CACHE": str(cache),
            }
            downloaded = []

            def downloader(url: str, destination: Path, verifier: Callable[[Path], bool]) -> None:
                downloaded.append((url, destination, verifier))

            self.assertEqual(
                ensure_makehuman_base(
                    environ=environment,
                    verifier=lambda candidate: candidate == mesh_path,
                    downloader=downloader,
                ),
                mesh_path,
            )
            self.assertEqual(downloaded, [])

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

    def test_local_measurements_do_not_rescale_the_head_or_each_other(self):
        levels = (0.0, 0.42, 0.50, 0.54, 0.58, 0.64, 0.69, 0.75, 0.80, 0.88, 0.90, 0.95, 1.0)
        source_vertices = tuple(
            (x, level, depth) for level in levels for x in (-1.0, 1.0) for depth in (-0.5, 0.5)
        )
        baseline = AvatarParameters()
        baseline_mapper = _make_source_fitted_mapper(source_vertices, baseline, 0.0)
        head_vertices = tuple(point for point in source_vertices if point[1] >= 0.90)
        baseline_head = tuple(baseline_mapper(point) for point in head_vertices)
        region_levels = {"hip": 0.50, "waist": 0.58, "chest": 0.69, "shoulder": 0.77}
        deltas = {"hip": 120.0, "waist": 100.0, "chest": 100.0, "shoulder": 50.0}

        for name, delta in deltas.items():
            with self.subTest(measurement=name):
                edited = baseline.with_measurements(**{name: baseline.measurement(name) + delta})
                mapper = _make_source_fitted_mapper(source_vertices, edited, 0.0)
                edited_head = tuple(mapper(point) for point in head_vertices)
                self.assertEqual(edited_head, baseline_head)
                region_point = (0.2, region_levels[name], 0.5)
                self.assertNotEqual(
                    mapper(region_point),
                    baseline_mapper(region_point),
                    f"{name} did not change its intended body region",
                )

    def test_torso_measurement_is_anisotropic_and_spares_distal_vertices(self) -> None:
        levels = (0.0, 0.42, 0.50, 0.54, 0.58, 0.64, 0.69, 0.75, 0.80, 0.88, 0.90, 0.95, 1.0)
        source_vertices = tuple(
            (x, level, depth) for level in levels for x in (-1.0, 1.0) for depth in (-0.5, 0.5)
        )
        baseline = AvatarParameters()
        edited = baseline.with_measurements(waist=baseline.measurement("waist") + 100.0)
        base_map = _make_source_fitted_mapper(source_vertices, baseline, 0.0)
        edited_map = _make_source_fitted_mapper(source_vertices, edited, 0.0)

        torso = (0.3, 0.58, 0.25)
        before, after = base_map(torso), edited_map(torso)
        lateral_delta = abs(after[0] - before[0])
        depth_delta = abs(after[1] - before[1])
        self.assertGreater(lateral_delta, depth_delta * 1.5)

        # At the same height, a point outside the canonical torso envelope is
        # not pulled outward by a waist edit.
        distal = (0.8, 0.58, 0.25)
        self.assertEqual(edited_map(distal), base_map(distal))

    def test_fit_rejects_non_finite_results_from_extreme_finite_vertices(self):
        source = parse_obj("""
        v -1e308 -1e308 0
        v 1e308 1e308 0
        v 0 0 1
        f 1 2 3
        """)
        with self.assertRaisesRegex(HumanoidMeshError, "invalid vertex coordinates"):
            fit_makehuman_mesh(source, AvatarParameters(skin_offset=0))

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

    def test_section_circumference_uses_trimesh_plane_intersections(self) -> None:
        """Measure a closed cube section using the vectorized Trimesh intersection API."""
        vertices = (
            (-1.0, -1.0, 0.0),
            (1.0, -1.0, 0.0),
            (1.0, 1.0, 0.0),
            (-1.0, 1.0, 0.0),
            (-1.0, -1.0, 1.0),
            (1.0, -1.0, 1.0),
            (1.0, 1.0, 1.0),
            (-1.0, 1.0, 1.0),
        )
        triangles = CUBE_TRIANGLES
        mesh = trimesh.Trimesh(
            vertices=np.asarray(vertices, dtype=np.float64),
            faces=np.asarray(triangles, dtype=np.int64),
            process=False,
        )

        circumference = _section_circumference(mesh, 0.5)

        require(
            condition=abs(circumference - 8.0) < 1e-9,
            message="unit cube section must have the expected square perimeter",
        )

    def test_compact_mesh_remaps_triangle_indices_with_numpy(self) -> None:
        """Preserve sorted source-index order when compacting mesh connectivity."""
        vertices = (
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (3.0, 0.0, 0.0),
            (4.0, 0.0, 0.0),
        )
        triangles = ((3, 1, 2), (2, 3, 2))

        compact_vertices, compact_triangles = compact_mesh(vertices, triangles)

        require(
            condition=compact_vertices == (vertices[1], vertices[2], vertices[3]),
            message="compaction must preserve the sorted source index order",
        )
        require(
            condition=compact_triangles == ((2, 0, 1), (1, 2, 1)),
            message="compaction must remap every triangle through the inverse index array",
        )

    def test_explicit_local_source_does_not_require_network(self):
        fd, path = tempfile.mkstemp(prefix="cloth-humanoid-", suffix=".obj")
        os.close(fd)
        try:
            Path(path).write_text("v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n", encoding="utf-8")
            loaded = load_makehuman_mesh(path)
            self.assertEqual(len(loaded.vertices), 3)
            self.assertEqual(loaded.triangles, ((0, 1, 2),))
        finally:
            Path(path).unlink()


if __name__ == "__main__":
    unittest.main()
