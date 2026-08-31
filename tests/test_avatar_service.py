import unittest

from AvatarModel import AvatarParameters, Pose
from AvatarService import AvatarService


class AvatarServiceTests(unittest.TestCase):
    def test_service_exposes_authoritative_measurements_and_pose(self):
        params = AvatarParameters(pose=Pose("sewing"))
        service = AvatarService(params)
        self.assertEqual(service.measurement("chest"), params.measurement("chest"))
        self.assertEqual(service.pose(), params.pose)
        self.assertEqual(service.skin_offset(), params.skin_offset)
        self.assertIn(("waist", params.measurement("waist")), service.measurements())

    def test_surface_and_collision_are_deterministic(self):
        service = AvatarService(AvatarParameters())
        first = service.surface()
        second = service.surface()
        self.assertEqual(first, second)
        self.assertEqual(first, service.collision_mesh())
        self.assertGreater(len(first[0]), 100)
        self.assertGreater(len(first[1]), 100)

    def test_landmark_lookup_is_stable(self):
        service = AvatarService(AvatarParameters())
        landmark = service.landmark("chest")
        self.assertEqual(landmark.name, "chest")
        self.assertEqual(len(landmark.position), 3)
        with self.assertRaises(KeyError):
            service.landmark("does-not-exist")

    def test_parameter_change_rebuilds_derived_surface_without_mutating_source(self):
        base = AvatarParameters()
        wider = AvatarParameters(base.measurements | {"chest": base.measurement("chest") + 100})
        self.assertEqual(AvatarService(base).measurement("chest"), 980.0)
        self.assertNotEqual(AvatarService(base).surface(), AvatarService(wider).surface())

    def test_invalid_service_parameter_type_is_rejected(self):
        with self.assertRaises(TypeError):
            AvatarService(object())


if __name__ == "__main__":
    unittest.main()
