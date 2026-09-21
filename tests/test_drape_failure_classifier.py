import unittest

from freecad_cloth.common.DrapeFailureClassifier import classify_drape, summarize_classification
from freecad_cloth.common.DrapeVisualSanity import inspect_drape, seam_correspondence_gap


class DrapeFailureClassifierTests(unittest.TestCase):
    def setUp(self):
        self.target = (
            (-100.0, -50.0, 0.0), (100.0, -50.0, 0.0),
            (-100.0, 50.0, 1750.0), (100.0, 50.0, 1750.0),
        )

    def test_empty(self):
        metrics = inspect_drape((), self.target)
        result = classify_drape(metrics, target_width=200.0)
        self.assertEqual(result.state, "empty")

    def test_nonfinite(self):
        metrics = inspect_drape(((0.0, 0.0, float("nan")),), self.target)
        result = classify_drape(metrics, target_width=200.0)
        self.assertEqual(result.state, "nonfinite")

    def test_clean_canonical_style_geometry(self):
        garment = (
            (-140.0, -90.0, 250.0), (140.0, -90.0, 250.0),
            (-140.0, 90.0, 1500.0), (140.0, 90.0, 1500.0),
        )
        metrics = inspect_drape(garment, self.target, target_height=1750.0, target_width=1000.0)
        result = classify_drape(metrics, components=1, target_width=1000.0)
        self.assertEqual(result.state, "structurally-plausible")
        self.assertIn("no failure evidence", result.reasons[0])

    def test_fragmented(self):
        garment = ((0.0, 0.0, 100.0), (100.0, 0.0, 100.0), (0.0, 0.0, 1000.0))
        metrics = inspect_drape(garment, self.target, target_height=1750.0, target_width=1000.0)
        result = classify_drape(metrics, components=2, target_width=1000.0)
        self.assertEqual(result.state, "fragmented")
        self.assertIn("multiple connected components", result.reasons[0])

    def test_broken_edge_correspondence(self):
        left = ((0.0, 0.0, 0.0), (100.0, 0.0, 0.0))
        right = ((1000.0, 0.0, 0.0), (1100.0, 0.0, 0.0))
        self.assertGreater(seam_correspondence_gap(left, right, 0, 0), 500.0)

    def test_edge_on_candidate(self):
        garment = ((0.0, 0.0, 700.0), (0.0, 10.0, 700.0), (0.0, 0.0, 710.0))
        metrics = inspect_drape(garment, self.target, target_height=1750.0, target_width=1000.0)
        result = classify_drape(metrics, target_width=1000.0)
        self.assertEqual(result.state, "edge-on-candidate")

    def test_detached_candidate_uses_normalized_clearance(self):
        garment = ((1000.0, 1000.0, 300.0), (1100.0, 1000.0, 300.0), (1000.0, 1000.0, 1500.0))
        metrics = inspect_drape(garment, self.target, target_height=1750.0, target_width=1000.0)
        result = classify_drape(metrics, target_width=200.0)
        self.assertEqual(result.state, "detached-candidate")

    def test_structurally_plausible(self):
        garment = (
            (-140.0, -90.0, 250.0), (140.0, -90.0, 250.0),
            (-140.0, 90.0, 1500.0), (140.0, 90.0, 1500.0),
        )
        metrics = inspect_drape(garment, self.target, target_height=1750.0, target_width=1000.0)
        result = classify_drape(metrics, target_width=1000.0)
        self.assertEqual(result.state, "structurally-plausible")
        data = summarize_classification(result)
        self.assertEqual(data["state"], "structurally-plausible")
        self.assertIsInstance(data["reasons"], list)


if __name__ == "__main__":
    unittest.main()
