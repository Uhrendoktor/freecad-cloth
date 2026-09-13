import unittest

from freecad_cloth.common.DrapeVisualSanity import inspect_drape, summarize


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

    def test_empty_mesh_is_classified(self):
        result = inspect_drape((), self.target, target_height=1750.0, target_width=200.0)
        self.assertEqual(result.state, "empty")
        self.assertFalse(result.finite)

    def test_nonfinite_mesh_is_classified(self):
        result = inspect_drape(((0.0, 0.0, float("nan")),), self.target)
        self.assertEqual(result.state, "nonfinite")
        self.assertFalse(result.finite)

    def test_detached_candidate_is_reported(self):
        garment = ((1000.0, 1000.0, 300.0), (1100.0, 1000.0, 300.0), (1000.0, 1000.0, 1500.0))
        result = inspect_drape(garment, self.target, target_height=1750.0, target_width=200.0)
        self.assertEqual(result.state, "detached-candidate")
        self.assertGreater(result.target_vertex_clearance, 100.0)

    def test_summary_is_stable(self):
        result = inspect_drape(((0.0, 0.0, 0.0), (10.0, 0.0, 10.0)), self.target)
        data = summarize(result)
        self.assertIn("state", data)
        self.assertIn("bounds", data)
        self.assertTrue(data["finite"])


if __name__ == "__main__":
    unittest.main()
