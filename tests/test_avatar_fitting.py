import json
import unittest

from AvatarFitting import BodyMeasurements, FittingScene, PiecePlacement


class AvatarFittingTests(unittest.TestCase):
    def test_measurements_are_valid_and_canonical(self):
        measurements = BodyMeasurements({"waist": 760, "height": 1700, "chest": 900})
        self.assertEqual(measurements.normalized(), (("chest", 900.0), ("height", 1700.0), ("waist", 760.0)))
        self.assertEqual(measurements.to_json(), '{"unit":"mm","values":{"chest":900.0,"height":1700.0,"waist":760.0}}')
        self.assertEqual(BodyMeasurements.from_json(measurements.to_json()), measurements)

    def test_invalid_measurement_is_rejected(self):
        with self.assertRaises(ValueError): BodyMeasurements({"waist": 0}).validate()
        with self.assertRaises(ValueError): BodyMeasurements({"waist": 10}, "inch").validate()

    def test_scene_metadata_is_deterministic(self):
        scene = FittingScene(BodyMeasurements({"hip": 960, "waist": 760}), "Avatar Collision Proxy", (PiecePlacement("piece-b", (10, 20, 30), 45), PiecePlacement("piece-a")))
        payload = scene.to_json()
        self.assertEqual(json.loads(payload)["pieces"], ["piece-a|0,0,0|0", "piece-b|10,20,30|45"])

    def test_duplicate_piece_placement_is_rejected(self):
        with self.assertRaises(ValueError): FittingScene(pieces=(PiecePlacement("piece"), PiecePlacement("piece"))).validate()

    def test_piece_placement_round_trip(self):
        placement = PiecePlacement("front", (1.5, -2.0, 3.25), 90.0)
        self.assertEqual(PiecePlacement.from_string(placement.to_string()), placement)


if __name__ == "__main__": unittest.main()
