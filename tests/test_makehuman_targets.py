import gzip
import os
import tempfile
import unittest
from pathlib import Path

from freecad_cloth.avatar.HumanoidMesh import _section_circumference
from freecad_cloth.avatar.MakeHumanTargets import (
    TARGETS_ENV,
    apply_targets,
    load_target,
    parse_target,
    target_directory,
)


class MakeHumanTargetTests(unittest.TestCase):
    def test_target_parser_restores_makehuman_axis_order_and_y_sign(self) -> None:
        target = parse_target(
            "# basemesh hm08\n0 0.125 -0.25 0.5\n2 -1.0 0.0 -0.75\n",
            "example.target",
        )
        self.assertEqual(
            target.offsets,
            ((0, (0.125, -0.5, -0.25)), (2, (-1.0, 0.75, 0.0))),
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
            self.assertEqual(fitted[0], (1.05, 2.15, 3.1))
            self.assertEqual(fitted[1], (-0.05, -0.25, 0.0))
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
            self.assertEqual(target.offsets, ((3, (0.0, 0.1, 0.2)),))
            with unittest.mock.patch.dict(os.environ, {TARGETS_ENV: str(root)}):
                self.assertEqual(target_directory(), root.resolve() / "targets")

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
            (0, 1, 5), (0, 5, 4),
            (1, 2, 6), (1, 6, 5),
            (2, 3, 7), (2, 7, 6),
            (3, 0, 4), (3, 4, 7),
        )
        self.assertAlmostEqual(
            _section_circumference(vertices, triangles, plane=0.5, max_width=10.0),
            12.0,
            places=4,
        )


if __name__ == "__main__":
    unittest.main()
