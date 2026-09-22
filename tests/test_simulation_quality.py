import sys
import unittest
from math import hypot
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freecad_cloth.pattern.PatternModel import PatternPiece
from freecad_cloth.simulation.SimulationQuality import FabricMaterial, QUALITY_PRESETS, preset, solver_parameters
from freecad_cloth.simulation.SimulationQualityRuntimeV2 import QualitySimulationProxy, _RUNTIME_BASES, quality_discretization
from freecad_cloth.simulation.SimulationMeshQuality import quality_piece_mesh


class SimulationQualityTests(unittest.TestCase):
    def test_quality_presets_are_monotonic_and_distinct(self):
        self.assertEqual(set(QUALITY_PRESETS), {"Fast", "Balanced", "Final"})
        self.assertGreater(preset("Fast").particle_distance, preset("Balanced").particle_distance)
        self.assertGreater(preset("Balanced").particle_distance, preset("Final").particle_distance)
        self.assertLess(preset("Fast").solver_iterations, preset("Final").solver_iterations)

    def test_material_defaults_and_solver_parameters(self):
        material = FabricMaterial()
        params = solver_parameters(preset("Final"), material)
        self.assertEqual(params["particle_distance"], 2.0)
        self.assertEqual(params["iterations"], 16)
        self.assertEqual(params["substeps"], 2)
        self.assertEqual(params["density_g_m2"], 150.0)
        self.assertEqual(params["thickness_mm"], 0.5)

    def test_material_validation_rejects_invalid_values(self):
        invalid = [
            ("density_g_m2", 0),
            ("thickness_mm", 0),
            ("stretch", 1.1),
            ("shear", -0.1),
            ("bend", 2),
            ("friction", -1),
        ]
        for field, value in invalid:
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    FabricMaterial(**{field: value}).validate()

    def test_unknown_quality_rejected(self):
        with self.assertRaises(ValueError):
            preset("Ultra")

    def test_quality_discretization_increases_with_smaller_particle_distance(self):
        coarse = quality_discretization(4, 320.0, preset("Fast").particle_distance)
        fine = quality_discretization(4, 320.0, preset("Final").particle_distance)
        self.assertGreater(fine, coarse)

    def test_pattern_mesh_density_changes_with_particle_distance(self):
        piece = PatternPiece("Test", [(0, 0), (100, 0), (100, 60), (0, 60)], id="test")
        piece_obj = type("Piece", (), {
            "SewingOutline": repr(piece.outline),
            "DraftingBoundary": repr(piece.outline),
            "PieceId": piece.id,
            "Placement": None,
        })()
        coarse = quality_piece_mesh(piece_obj, 100.0, 20.0)
        fine = quality_piece_mesh(piece_obj, 100.0, 5.0)
        self.assertGreater(len(fine[0]), len(coarse[0]))

    def test_refinement_preserves_authored_boundary_and_materially_tessellates(self):
        piece = PatternPiece("Test", [(0, 0), (100, 0), (100, 60), (0, 60)], id="test")
        piece_obj = type("Piece", (), {
            "SewingOutline": repr(piece.outline),
            "DraftingBoundary": repr(piece.outline),
            "PieceId": piece.id,
            "Placement": None,
        })()
        positions, triangles, boundary = quality_piece_mesh(piece_obj, 100.0, 2.0)
        boundary_points = {positions[index][:2] for edge in boundary for index in edge}
        for outline_point in piece.outline:
            self.assertIn(outline_point, boundary_points)
        self.assertEqual(len(boundary), len(piece.outline))
        self.assertGreater(sum(len(edge) for edge in boundary), len(piece.outline))
        self.assertGreater(len(triangles), 100)
        self.assertGreater(len(positions), len(boundary_points))

    def test_quality_seam_edges_have_interior_particles_and_spacing_bound(self):
        piece = PatternPiece("Test", [(0, 0), (120, 0), (120, 60), (0, 60)], id="test")
        piece_obj = type("Piece", (), {
            "SewingOutline": repr(piece.outline),
            "DraftingBoundary": repr(piece.outline),
            "PieceId": piece.id,
            "Placement": None,
        })()
        spacing = 20.0
        positions, _triangles, boundary = quality_piece_mesh(piece_obj, 100.0, spacing)
        self.assertEqual(len(boundary), len(piece.outline))
        for edge in boundary:
            self.assertGreaterEqual(len(edge), 3)
            distances = [
                ((positions[a][0] - positions[b][0]) ** 2 + (positions[a][1] - positions[b][1]) ** 2) ** 0.5
                for a, b in zip(edge, edge[1:])
            ]
            self.assertLessEqual(max(distances), spacing + 1e-9)

    def test_refined_tunic_edges_preserve_authored_order(self):
        outline = [
            (0.0, 0.0), (600.0, 0.0), (520.0, 590.4), (447.2, 698.4),
            (332.8, 648.0), (187.2, 648.0), (72.8, 698.4), (0.0, 590.4),
        ]
        piece = PatternPiece("Tunic", outline, id="tunic")
        piece_obj = type("Piece", (), {
            "SewingOutline": repr(piece.outline),
            "DraftingBoundary": repr(piece.outline),
            "PieceId": piece.id,
            "Placement": None,
        })()
        spacing = 20.0
        positions, _triangles, boundary = quality_piece_mesh(piece_obj, 100.0, spacing)

        self.assertEqual(len(boundary), len(outline))
        for edge_index, edge in enumerate(boundary):
            self.assertGreaterEqual(len(edge), 3)
            start = outline[edge_index]
            end = outline[(edge_index + 1) % len(outline)]
            self.assertAlmostEqual(positions[edge[0]][0], start[0], places=7)
            self.assertAlmostEqual(positions[edge[0]][1], start[1], places=7)
            self.assertAlmostEqual(positions[edge[-1]][0], end[0], places=7)
            self.assertAlmostEqual(positions[edge[-1]][1], end[1], places=7)
            distances = [
                hypot(
                    positions[left][0] - positions[right][0],
                    positions[left][1] - positions[right][1],
                )
                for left, right in zip(edge, edge[1:])
            ]
            self.assertLessEqual(max(distances), spacing + 1e-7)

    def test_quality_proxy_keeps_solver_state_outside_serialized_object_dict(self):
        """Guard the reload path without placing the non-serializable solver in __dict__."""
        proxy = QualitySimulationProxy()
        original = _RUNTIME_BASES[proxy]
        self.assertNotIn("_base", proxy.__dict__)
        self.assertEqual(proxy.last_steps, 0)
        restored = proxy._base_or_restore()
        self.assertIs(restored, original)
        proxy.onDocumentRestored(None)
        self.assertIsNot(_RUNTIME_BASES[proxy], restored)
        self.assertEqual(proxy.last_steps, 0)


if __name__ == "__main__":
    unittest.main()
