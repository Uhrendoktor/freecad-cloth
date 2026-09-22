import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freecad_cloth.pattern.PatternModel import PatternPiece
from freecad_cloth.simulation.SimulationQuality import FabricMaterial, QUALITY_PRESETS, preset, solver_parameters
from freecad_cloth.simulation.SimulationQualityRuntimeV2 import QualitySimulationProxy, _RUNTIME_BASES, quality_discretization
from freecad_cloth.simulation.SimulationMeshQuality import quality_piece_mesh, refine_linear_boundary


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


    def test_linear_boundary_refinement_is_deterministic_and_capped(self):
        from freecad_cloth.pattern.PatternGeometry import rectangle

        pattern = rectangle(100.0, 60.0)
        refined, subedge_map = refine_linear_boundary(pattern, 20.0)

        authored_ids = [segment.id for segment in pattern.segments]
        self.assertEqual(set(subedge_map.values()), set(authored_ids))
        self.assertEqual(
            [segment.id for segment in refined.segments],
            [
                "bottom::simulation-sub::0",
                "bottom::simulation-sub::1",
                "bottom::simulation-sub::2",
                "bottom::simulation-sub::3",
                "bottom::simulation-sub::4",
                "right::simulation-sub::0",
                "right::simulation-sub::1",
                "right::simulation-sub::2",
                "top::simulation-sub::0",
                "top::simulation-sub::1",
                "top::simulation-sub::2",
                "top::simulation-sub::3",
                "top::simulation-sub::4",
                "left::simulation-sub::0",
                "left::simulation-sub::1",
                "left::simulation-sub::2",
            ],
        )
        for segment in refined.segments:
            self.assertLessEqual(segment.length(), 20.0 + 1e-9)

    def test_quality_boundary_is_contiguous_per_authored_edge_and_spacing_bounded(self):
        piece = PatternPiece("Test", [(0, 0), (100, 0), (100, 60), (0, 60)], id="test")
        piece_obj = type("Piece", (), {
            "SewingOutline": repr(piece.outline),
            "DraftingBoundary": repr(piece.outline),
            "PieceId": piece.id,
            "Placement": None,
        })()
        positions, _triangles, boundary = quality_piece_mesh(piece_obj, 100.0, 20.0)

        self.assertEqual(len(boundary), len(piece.outline))
        for edge_index, chain in enumerate(boundary):
            self.assertGreaterEqual(len(chain), 2)
            self.assertEqual(positions[chain[0]][:2], piece.outline[edge_index])
            end_index = (edge_index + 1) % len(piece.outline)
            self.assertEqual(positions[chain[-1]][:2], piece.outline[end_index])
            for a, b in zip(chain, chain[1:]):
                span = (
                    (positions[a][0] - positions[b][0]) ** 2
                    + (positions[a][1] - positions[b][1]) ** 2
                ) ** 0.5
                self.assertLessEqual(span, 20.0 + 1e-6)

    def test_refined_tunic_edges_preserve_authored_order_and_spacing(self):
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
        for edge_index, chain in enumerate(boundary):
            self.assertGreaterEqual(len(chain), 3)
            self.assertAlmostEqual(positions[chain[0]][0], outline[edge_index][0], places=7)
            self.assertAlmostEqual(positions[chain[0]][1], outline[edge_index][1], places=7)
            end_index = (edge_index + 1) % len(outline)
            self.assertAlmostEqual(positions[chain[-1]][0], outline[end_index][0], places=7)
            self.assertAlmostEqual(positions[chain[-1]][1], outline[end_index][1], places=7)
            for left, right in zip(chain, chain[1:]):
                span = (
                    (positions[left][0] - positions[right][0]) ** 2
                    + (positions[left][1] - positions[right][1]) ** 2
                ) ** 0.5
                self.assertLessEqual(span, spacing + 1e-6)

    def test_sewing_semantic_edge_lookup_remains_authored_ordinal(self):
        from types import SimpleNamespace
        from freecad_cloth.pattern.PatternObjects import _edge_records, _seam_edge_id
        from freecad_cloth.sewing.SewingObjects import _seam_edge_index

        piece = SimpleNamespace(
            PieceId="test",
            Width=100.0,
            Height=60.0,
            SewingOutline=repr([(0, 0), (100, 0), (100, 60), (0, 60)]),
        )
        records = _edge_records(piece)
        self.assertEqual([record["id"] for record in records], [
            "test:edge:0",
            "test:edge:1",
            "test:edge:2",
            "test:edge:3",
        ])
        edge_id, signature = _seam_edge_id(piece, 0, "A")
        seam = SimpleNamespace(EdgeAId=edge_id, EdgeASignature=signature, EdgeA=0)
        resolved = _seam_edge_index(piece, seam, "A")
        self.assertEqual(resolved, 0)
        self.assertNotIn("::simulation-sub::", seam.EdgeAId)

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
        # Constrained Delaunay keeps the authored pattern vertices as the
        # semantic boundary; refinement adds interior vertices and triangles.
        self.assertEqual(len(boundary), len(piece.outline))
        self.assertGreater(len(triangles), 100)
        self.assertGreater(sum(len(chain) for chain in boundary), len(piece.outline))
        self.assertGreater(len(positions), len(piece.outline))
        for edge_index, chain in enumerate(boundary):
            start = positions[chain[0]][:2]
            end = positions[chain[-1]][:2]
            expected_end = piece.outline[(edge_index + 1) % len(piece.outline)]
            for actual, expected in zip(start, piece.outline[edge_index]):
                self.assertAlmostEqual(actual, expected, places=7)
            for actual, expected in zip(end, expected_end):
                self.assertAlmostEqual(actual, expected, places=7)

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
