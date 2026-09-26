import unittest

from freecad_cloth.common.DrapeFailureClassifier import classify_drape, summarize_classification
from freecad_cloth.common.DrapeVisualSanity import assert_drape_diagnostics
from freecad_cloth.common.DrapeVisualSanity import inspect_drape, mesh_shape_sanity, seam_correspondence_gap, summarize
from freecad_cloth.common.MeshValidation import validate_mesh


class DrapeVisualSanityTests(unittest.TestCase):
    def setUp(self):
        self.target = (
            (-100.0, -50.0, 0.0), (100.0, -50.0, 0.0),
            (-100.0, 50.0, 1750.0), (100.0, 50.0, 1750.0),
        )

    def test_reports_structurally_plausible_drape(self):
        garment = (
            (-140.0, -90.0, 250.0), (140.0, -90.0, 250.0),
            (-140.0, 90.0, 1500.0), (140.0, 90.0, 1500.0),
        )
        result = inspect_drape(garment, self.target, target_height=1750.0, target_width=1000.0)
        self.assertTrue(result.finite)
        self.assertEqual(result.state, "structurally-plausible")
        self.assertGreater(result.vertical_span_ratio, 0.6)
        self.assertEqual(result.vertices, 4)

    def test_vertical_ratio_uses_z_not_largest_footprint_axis(self):
        garment = (
            (-1500.0, -40.0, 100.0), (1500.0, -40.0, 100.0),
            (-1500.0, 40.0, 200.0), (1500.0, 40.0, 200.0),
        )
        result = inspect_drape(garment, self.target, target_height=1750.0, target_width=3000.0)
        self.assertAlmostEqual(result.vertical_span_ratio, 100.0 / 1750.0)
        self.assertAlmostEqual(result.lateral_span_ratio, 3000.0 / 3000.0)
        self.assertEqual(result.state, "short-drape-candidate")

    def test_lateral_ratio_uses_larger_footprint_axis(self):
        garment = (
            (-20.0, -900.0, 300.0), (20.0, -900.0, 300.0),
            (-20.0, 900.0, 1500.0), (20.0, 900.0, 1500.0),
        )
        result = inspect_drape(garment, self.target, target_height=1750.0, target_width=2000.0)
        self.assertAlmostEqual(result.vertical_span_ratio, 1200.0 / 1750.0)
        self.assertAlmostEqual(result.lateral_span_ratio, 1800.0 / 2000.0)

    def test_empty_mesh_is_classified(self):
        result = inspect_drape((), self.target, target_height=1750.0, target_width=200.0)
        self.assertEqual(result.state, "empty")
        self.assertFalse(result.finite)

    def test_nonfinite_mesh_is_classified(self):
        result = inspect_drape(((0.0, 0.0, float("nan")),), self.target)
        self.assertEqual(result.state, "nonfinite")
        self.assertFalse(result.finite)

    def test_missing_target_is_classified_before_geometry_quality(self):
        garment = ((-100.0, 0.0, 100.0), (100.0, 0.0, 1500.0))
        result = inspect_drape(garment, (), target_height=1750.0, target_width=1000.0)
        self.assertEqual(result.state, "missing-target")
        self.assertIsNone(result.target_vertex_clearance)

    def test_detached_candidate_is_reported(self):
        garment = ((1000.0, 1000.0, 300.0), (1100.0, 1000.0, 300.0), (1000.0, 1000.0, 1500.0))
        result = inspect_drape(garment, self.target, target_height=1750.0, target_width=200.0)
        self.assertEqual(result.state, "detached-candidate")
        self.assertGreater(result.target_vertex_clearance, 100.0)

    def test_mesh_shape_sanity_rejects_long_edge_spike(self):
        vertices = (
            (0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 10.0, 0.0),
            (0.0, 10.0, 0.0), (80.0, 80.0, 0.0),
        )
        triangles = ((0, 1, 2), (0, 2, 3), (2, 4, 3))
        result = mesh_shape_sanity(vertices, triangles)
        self.assertTrue(result["finite"])
        self.assertGreater(result["edge_spike_ratio"], 4.0)
        self.assertGreater(result["spike_edge_fraction"], 0.0)

    def test_mesh_shape_sanity_accepts_regular_grid(self):
        vertices = (
            (0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (20.0, 0.0, 0.0),
            (0.0, 10.0, 0.0), (10.0, 10.0, 0.0), (20.0, 10.0, 0.0),
        )
        triangles = ((0, 1, 4), (0, 4, 3), (1, 2, 5), (1, 5, 4))
        result = mesh_shape_sanity(vertices, triangles)
        self.assertTrue(result["finite"])
        self.assertLess(result["edge_spike_ratio"], 2.0)
        self.assertAlmostEqual(result["footprint_aspect_ratio"], 2.0)

    def test_clean_canonical_style_mesh_has_one_component(self):
        vertices = (
            (-140.0, -90.0, 250.0), (140.0, -90.0, 250.0),
            (-140.0, 90.0, 1500.0), (140.0, 90.0, 1500.0),
        )
        triangles = ((0, 1, 2), (1, 3, 2))
        result = validate_mesh(vertices, triangles, prefer_trimesh=False)
        self.assertEqual(result.components, 1)
        self.assertTrue(result.finite)

    def test_fragmented_geometry_has_two_components(self):
        vertices = (
            (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0),
            (100.0, 0.0, 0.0), (101.0, 0.0, 0.0), (100.0, 1.0, 0.0),
        )
        triangles = ((0, 1, 2), (3, 4, 5))
        result = validate_mesh(vertices, triangles, prefer_trimesh=False)
        self.assertEqual(result.components, 2)

    def test_seam_correspondence_is_clean_for_matching_canonical_edges(self):
        boundary = (
            (0.0, 0.0, 0.0), (100.0, 0.0, 0.0),
            (100.0, 100.0, 0.0), (0.0, 100.0, 0.0),
        )
        self.assertEqual(seam_correspondence_gap(boundary, boundary, 0, 0), 0.0)

    def test_seam_correspondence_detects_obvious_detachment(self):
        left = ((0.0, 0.0, 0.0), (100.0, 0.0, 0.0))
        right = ((250.0, 0.0, 0.0), (350.0, 0.0, 0.0))
        self.assertEqual(seam_correspondence_gap(left, right, 0, 0), 250.0)

    def test_summary_is_stable(self):
        result = inspect_drape(((0.0, 0.0, 0.0), (10.0, 0.0, 10.0)), self.target)
        data = summarize(result)
        self.assertIn("state", data)
        self.assertIn("bounds", data)
        self.assertTrue(data["finite"])

    def test_failure_classifier_reports_fragmentation(self):
        garment = ((0.0, 0.0, 100.0), (100.0, 0.0, 100.0), (0.0, 0.0, 1000.0))
        metrics = inspect_drape(garment, self.target, target_height=1750.0, target_width=1000.0)
        result = classify_drape(metrics, components=2, target_width=1000.0)
        self.assertEqual(result.state, "fragmented")
        self.assertIn("multiple connected components", result.reasons[0])

    def test_failure_classifier_reports_edge_on_candidate(self):
        garment = ((0.0, 0.0, 700.0), (0.0, 10.0, 700.0), (0.0, 0.0, 710.0))
        metrics = inspect_drape(garment, self.target, target_height=1750.0, target_width=1000.0)
        result = classify_drape(metrics, target_width=1000.0)
        self.assertEqual(result.state, "edge-on-candidate")

    def test_failure_classifier_normalizes_detachment(self):
        garment = ((1000.0, 1000.0, 300.0), (1100.0, 1000.0, 300.0), (1000.0, 1000.0, 1500.0))
        metrics = inspect_drape(garment, self.target, target_height=1750.0, target_width=1000.0)
        result = classify_drape(metrics, target_width=200.0)
        self.assertEqual(result.state, "detached-candidate")

    def test_failure_classifier_summary_is_json_ready(self):
        garment = (
            (-140.0, -90.0, 250.0), (140.0, -90.0, 250.0),
            (-140.0, 90.0, 1500.0), (140.0, 90.0, 1500.0),
        )
        metrics = inspect_drape(garment, self.target, target_height=1750.0, target_width=1000.0)
        result = classify_drape(metrics, target_width=1000.0)
        data = summarize_classification(result)
        self.assertEqual(data["state"], "structurally-plausible")
        self.assertIsInstance(data["reasons"], list)

    def test_drape_diagnostics_accepts_clean_attached_result(self):
        assert_drape_diagnostics((
            {
                "panel": "Front",
                "failure_classification": {"state": "structurally-plausible"},
                "diagnostics": [],
            },
            {
                "panel": "Back",
                "failure_classification": {"state": "structurally-plausible"},
                "diagnostics": ["target-clearance-candidate"],
            },
        ))

    def test_drape_diagnostics_rejects_detached_and_collapsed_results(self):
        for record in (
            {
                "panel": "Front",
                "failure_classification": {"state": "detached-candidate"},
                "diagnostics": [],
            },
            {
                "panel": "Back",
                "failure_classification": {"state": "structurally-plausible"},
                "diagnostics": ["collapsed-candidate"],
            },
            {
                "panel": "Side",
                "failure_classification": {"state": "structurally-plausible"},
                "diagnostics": ["below-hem-candidate"],
            },
            {
                "panel": "Lateral",
                "failure_classification": {"state": "structurally-plausible"},
                "diagnostics": ["lateral-detached-candidate"],
            },
        ):
            with self.assertRaisesRegex(RuntimeError, "drape visual acceptance failed closed"):
                assert_drape_diagnostics((record,))



if __name__ == "__main__":
    unittest.main()

