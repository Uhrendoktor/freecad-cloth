import unittest

from AvatarModel import AvatarParameters


class AvatarModelTests(unittest.TestCase):
    def test_defaults_and_round_trip(self):
        avatar = AvatarParameters({})
        self.assertEqual(avatar.measurement("height"), 1700.0)
        self.assertEqual(AvatarParameters.from_json(avatar.to_json()), avatar)

    def test_measurement_change_round_trips(self):
        avatar = AvatarParameters({"chest": 1020.0, "waist": 840.0})
        restored = AvatarParameters.from_json(avatar.to_json())
        self.assertEqual(restored.measurement("chest"), 1020.0)
        self.assertEqual(restored.measurement("waist"), 840.0)

    def test_invalid_measurements_rejected(self):
        with self.assertRaises(ValueError):
            AvatarParameters({"height": 0})
        with self.assertRaises(ValueError):
            AvatarParameters({"waist": 950, "chest": 900})

    def test_pose_and_offset_validation(self):
        with self.assertRaises(ValueError):
            AvatarParameters({}, skin_offset=-1)
        with self.assertRaises(ValueError):
            AvatarParameters({}, pose="walking")


if __name__ == "__main__":
    unittest.main()
