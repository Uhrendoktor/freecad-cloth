import gzip
import math
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from freecad_cloth.avatar.AvatarModel import AvatarParameters
from freecad_cloth.avatar.HumanoidMesh import (
    _make_source_fitted_mapper,
    _section_circumference,
)
from freecad_cloth.avatar.MakeHumanTargets import (
    TARGETS_ENV,
    apply_measurement_targets,
    apply_targets,
    load_target,
    parse_target,
    resolve_target,
    target_directory,
)


class MakeHumanTargetTests(unittest.TestCase):
    def test_target_parser_preserves_makehuman_native_axis_order(self) -> None:
        target = parse_target(
            "# basemesh hm08\n0 0.125 -0.25 0.5\n2 -1.0 0.0 -0.75\n",
            "example.target",
        )
        self.assertEqual(
            target.offsets,
            ((0, (0.125, -0.25, 0.5)), (2, (-1.0, 0.0, -0.75))),
        )

    def test_target_parser_rejects_non_finite_and_negative_indices(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-negative"):
            parse_target("-1 0 0 0")
        with self.assertRaisesRegex(ValueError, "finite"):
            parse_target("0 nan 0 0")

    def test_sparse_targets_apply_weight_and_ignore_out_of_range_vertices(self) -> None:
        with tempfile.TemporaryDirectory(prefix="cloth-targets-") as directory:
            root = Path(directory)
            target_dir = root / "torso"
            target_dir.mkdir()
            (target_dir / "measure-waist-circ-incr.target").write_text(
                "# HM08 target\n0 0.1 0.2 -0.3\n1 -0.1 0.0 0.5\n7 9 9 9\n",
                encoding="utf-8",
            )
            vertices = ((1.0, 2.0, 3.0), (0.0, 0.0, 0.0), (7.0, 8.0, 9.0))
            fitted = apply_targets(vertices, {"measure-waist-circ-incr": 0.5}, root)
            self.assertEqual(fitted[0], (1.05, 2.1, 2.85))
            self.assertEqual(fitted[1], (-0.05, 0.0, 0.25))
            self.assertEqual(fitted[2], vertices[2])

    def test_gzip_targets_load_and_installed_library_is_discovered(self) -> None:
        with tempfile.TemporaryDirectory(prefix="cloth-targets-") as directory:
            root = Path(directory)
            target_dir = root / "targets" / "breast"
            target_dir.mkdir(parents=True)
            target_path = target_dir / "breast-dist-incr.target.gz"
            with gzip.open(target_path, "wt", encoding="utf-8") as stream:
                stream.write("3 0.0 0.2 -0.1\n")
            target = load_target(target_path)
            self.assertEqual(target.offsets, ((3, (0.0, 0.2, -0.1)),))
            with patch.dict(os.environ, {TARGETS_ENV: str(root)}):
                self.assertEqual(target_directory(), root.resolve() / "targets")

    def test_makehuman_targets_npz_archive_uses_native_coordinate_offsets(self) -> None:
        with tempfile.TemporaryDirectory(prefix="cloth-target-archive-") as directory:
            root = Path(directory)
            archive = root / "targets.npz"
            with patch.dict(os.environ, {TARGETS_ENV: str(root)}):
                self.assertEqual(target_directory(), root.resolve())
            np.savez_compressed(
                archive,
                **{
                    "targets/torso/measure-waist-circ-incr.index": np.array(
                        [0, 2], dtype=np.uint16
                    ),
                    "targets/torso/measure-waist-circ-incr.vector": np.array(
                        [[100, -250, 300], [-100, 0, 500]], dtype=np.int16
                    ),
                },
            )
            reference = resolve_target("torso/measure-waist-circ-incr", root)
            self.assertIsNotNone(reference)
            assert reference is not None
            target = load_target(reference)
            self.assertEqual(
                target.offsets,
                ((0, (0.1, -0.25, 0.3)), (2, (-0.1, 0.0, 0.5))),
            )
            vertices = ((1.0, 2.0, 3.0), (4.0, 5.0, 6.0), (7.0, 8.0, 9.0))
            blended = apply_targets(vertices, {"torso/measure-waist-circ-incr": 0.5}, root)
            self.assertEqual(blended[0], (1.05, 1.875, 3.15))
            self.assertEqual(blended[1], vertices[1])
            self.assertEqual(blended[2], (6.95, 8.0, 9.25))

    def test_target_lookup_falls_back_to_sibling_archive_for_partial_loose_tree(self) -> None:
        with tempfile.TemporaryDirectory(prefix="cloth-target-fallback-") as directory:
            root = Path(directory)
            loose = root / "targets"
            loose.mkdir()
            (loose / "custom.target").write_text("0 1 0 0\n", encoding="utf-8")
            np.savez_compressed(
                root / "targets.npz",
                **{
                    "targets/torso/measure-waist-circ-incr.index": np.array([0]),
                    "targets/torso/measure-waist-circ-incr.vector": np.array(
                        [[100, 0, 0]], dtype=np.int16
                    ),
                },
            )
            reference = resolve_target("torso/measure-waist-circ-incr", loose)
            self.assertIsNotNone(reference)
            assert reference is not None
            self.assertEqual(reference.path, (root / "targets.npz").resolve())

    def test_breast_fullness_uses_volume_target(self) -> None:
        with tempfile.TemporaryDirectory(prefix="cloth-breast-target-") as directory:
            root = Path(directory)
            target_dir = root / "breast"
            target_dir.mkdir()
            (target_dir / "breast-volume-vert-up.target").write_text(
                "0 0.2 0.1 -0.2\\n", encoding="utf-8"
            )
            parameters = AvatarParameters(gender=0.5, breast_size=0.5)
            vertices = ((1.0, 2.0, 3.0),)
            with patch.dict(os.environ, {TARGETS_ENV: str(root)}):
                fitted = apply_measurement_targets(vertices, parameters)
            self.assertAlmostEqual(fitted[0][0], 1.1)
            self.assertAlmostEqual(fitted[0][1], 2.05)
            self.assertAlmostEqual(fitted[0][2], 2.9)

    def test_torso_mapper_calibrates_named_waist_contour(self) -> None:
        source_vertices = []
        ring_count = 24
        for normalized_height in (0.579, 0.581):
            source_y = normalized_height * 2.0 - 1.0
            for index in range(ring_count):
                angle = (2.0 * math.pi * index) / ring_count
                source_vertices.append((0.30 * math.cos(angle), source_y, 0.50 * math.sin(angle)))
        # Unconnected extrema define the HM08-wide calibration frame, while
        # the closed rings represent a waist contour inside the trunk envelope.
        source_vertices.extend(((-1.0, -1.0, -1.0), (1.0, 1.0, 1.0)))
        triangles = []
        for index in range(ring_count):
            following = (index + 1) % ring_count
            lower_left = index
            lower_right = following
            upper_left = ring_count + index
            upper_right = ring_count + following
            triangles.extend(
                (
                    (lower_left, lower_right, upper_right),
                    (lower_left, upper_right, upper_left),
                )
            )

        parameters = AvatarParameters()
        mapper = _make_source_fitted_mapper(
            source_vertices, parameters, 0.0, source_triangles=triangles
        )
        fitted = tuple(mapper(point) for point in source_vertices)
        actual = _section_circumference(
            fitted,
            triangles,
            plane=parameters.measurement("height") * 0.58,
            vertical_axis=2,
            max_width=600.0,
        )
        self.assertGreater(actual, 0.0)
        self.assertAlmostEqual(actual, parameters.measurement("waist"), delta=5.0)

    def test_mesh_section_returns_polygon_perimeter(self) -> None:
        vertices = (
            (-1.0, -2.0, 0.0),
            (1.0, -2.0, 0.0),
            (1.0, 2.0, 0.0),
            (-1.0, 2.0, 0.0),
            (-1.0, -2.0, 1.0),
            (1.0, -2.0, 1.0),
            (1.0, 2.0, 1.0),
            (-1.0, 2.0, 1.0),
        )
        triangles = (
            (0, 1, 5),
            (0, 5, 4),
            (1, 2, 6),
            (1, 6, 5),
            (2, 3, 7),
            (2, 7, 6),
            (3, 0, 4),
            (3, 4, 7),
        )
        self.assertAlmostEqual(
            _section_circumference(vertices, triangles, plane=0.5, max_width=10.0),
            12.0,
            places=4,
        )


if __name__ == "__main__":
    unittest.main()
