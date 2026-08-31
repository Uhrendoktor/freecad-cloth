import json
import unittest

from AvatarFitting import ArrangementPoint, BodyMeasurements, BoundingVolume, FittingScene, PiecePlacement
from AvatarModel import AvatarParameters, DEFAULT_MEASUREMENTS, Pose, generate_mesh
from AvatarService import AvatarService


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

    def test_arrangement_point_round_trip_and_mirror(self):
        point = ArrangementPoint("shoulder-left", 120, 80, 15, "left", 10, "shoulders")
        self.assertEqual(ArrangementPoint.from_string(point.to_string()), point)
        mirrored = point.mirrored()
        self.assertEqual(mirrored.name, "shoulder-left.mirror")
        self.assertEqual(mirrored.x, -120.0)
        self.assertEqual(mirrored.wrap_direction, "right")
        self.assertEqual(mirrored.rotation_z, -10.0)

    def test_invalid_arrangement_point_and_volume_are_rejected(self):
        with self.assertRaises(ValueError): ArrangementPoint("", wrap_direction="front").validate()
        with self.assertRaises(ValueError): ArrangementPoint("p", wrap_direction="inside").validate()
        with self.assertRaises(ValueError): BoundingVolume("body", size=(1, 0, 2)).validate()

    def test_fitting_scene_round_trip_preserves_arrangement_metadata(self):
        scene = FittingScene(BodyMeasurements({"waist": 760}), "Avatar", (PiecePlacement("front", (1, 2, 3), 15),), (ArrangementPoint("chest", 10, 20, 5, "front", 30, "torso"),), (BoundingVolume("torso", (0, 0, 50), (400, 250, 800)),), False)
        restored = FittingScene.from_json(scene.to_json())
        self.assertEqual(restored, scene)
        self.assertFalse(restored.symmetry_enabled)
        self.assertEqual(restored.arrangement_map()["chest"].position(), (10.0, 20.0, 5.0))

    def test_mannequin_is_deterministic_and_landmarked(self):
        params = AvatarParameters()
        first = generate_mesh(params)
        second = generate_mesh(params)
        self.assertEqual(first, second)
        self.assertGreater(len(first[0]), 100)
        self.assertGreater(len(first[1]), 100)
        self.assertGreaterEqual({p.name for p in first[2]}, {"neck", "chest", "waist", "hip", "shoulder_left", "shoulder_right"})

    def test_mannequin_measurement_change_is_parametric(self):
        params = AvatarParameters()
        wider = params.with_measurements(chest=params.measurement("chest") + 100)
        self.assertEqual(params.measurement("chest"), DEFAULT_MEASUREMENTS["chest"])
        self.assertNotEqual(generate_mesh(params)[0], generate_mesh(wider)[0])

    def test_mannequin_skin_offset_and_pose_persist(self):
        base = AvatarParameters(skin_offset=0)
        padded = AvatarParameters(skin_offset=8)
        self.assertNotEqual(generate_mesh(base)[0], generate_mesh(padded)[0])
        params = AvatarParameters(pose=Pose("sewing"))
        self.assertEqual(AvatarParameters.from_json(params.to_json()), params)

    def test_avatar_service_exposes_stable_downstream_contract(self):
        params = AvatarParameters(pose=Pose("sewing"))
        service = AvatarService(params)
        self.assertEqual(service.parameters(), params)
        self.assertEqual(service.measurement("chest"), params.measurement("chest"))
        self.assertEqual(service.pose(), params.pose)
        self.assertEqual(service.skin_offset(), params.skin_offset)
        self.assertIn(("waist", params.measurement("waist")), service.measurements())
        self.assertEqual(service.surface(), service.collision_mesh())
        self.assertGreater(len(service.surface()[0]), 100)
        self.assertEqual(service.landmark("chest").name, "chest")
        with self.assertRaises(KeyError): service.landmark("does-not-exist")

    def test_avatar_service_derives_geometry_from_new_parameters(self):
        base = AvatarParameters()
        wider = base.with_measurements(chest=base.measurement("chest") + 100)
        self.assertNotEqual(AvatarService(base).surface(), AvatarService(wider).surface())

    def test_invalid_avatar_service_parameter_type_is_rejected(self):
        with self.assertRaises(TypeError): AvatarService(object())

    def test_invalid_mannequin_measurements_are_rejected(self):
        with self.assertRaises(ValueError): AvatarParameters().with_measurements(underbust=1200, chest=1000)


if __name__ == "__main__": unittest.main()
