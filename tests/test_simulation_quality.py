import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PatternModel import PatternPiece
from SimulationQuality import FabricMaterial, QUALITY_PRESETS, preset, solver_parameters
from SimulationQualityRuntimeV2 import quality_discretization
from SimulationMeshQuality import quality_piece_mesh


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
        self.assertEqual(len(boundary), 4)
        self.assertEqual(len(triangles), 162)
        self.assertEqual([positions[i][:2] for i in boundary], piece.outline)
        self.assertGreater(len(positions), len(boundary))


if __name__ == "__main__":
    unittest.main()
