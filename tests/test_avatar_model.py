import unittest
from AvatarModel import AvatarParameters, DEFAULT_MEASUREMENTS, generate_mesh

class AvatarModelTests(unittest.TestCase):
    def test_defaults_and_round_trip(self):
        avatar=AvatarParameters({}); self.assertEqual(avatar.measurement("height"),DEFAULT_MEASUREMENTS["height"]); self.assertEqual(AvatarParameters.from_json(avatar.to_json()),avatar); self.assertGreater(len(avatar.measurements),10)
    def test_measurement_change_round_trips(self):
        avatar=AvatarParameters({"chest":1020.0,"waist":840.0}); restored=AvatarParameters.from_json(avatar.to_json()); self.assertEqual(restored.measurement("chest"),1020.0); self.assertEqual(restored.measurement("waist"),840.0)
    def test_invalid_measurements_rejected(self):
        with self.assertRaises(ValueError): AvatarParameters({"height":0})
        with self.assertRaises(ValueError): AvatarParameters({"chest":500})
        with self.assertRaises(ValueError): AvatarParameters({"inseam":1800})
    def test_pose_and_offset_validation(self):
        with self.assertRaises(ValueError): AvatarParameters({},skin_offset=-1)
        with self.assertRaises(ValueError): AvatarParameters({},pose=__import__("AvatarModel").Pose("walking"))
    def test_geometry_is_deterministic_and_has_landmarks(self):
        avatar=AvatarParameters({}); a=generate_mesh(avatar); b=generate_mesh(avatar); self.assertEqual(a,b); self.assertGreater(len(a[0]),100); self.assertGreater(len(a[1]),100); names={x.name for x in a[2]}; self.assertTrue({"neck","chest","waist","hip","shoulder_left","shoulder_right"}<=names)
    def test_skin_offset_changes_collision_geometry_without_measurements(self):
        base=AvatarParameters({},skin_offset=0); offset=AvatarParameters({},skin_offset=12); self.assertEqual(base.measurements,offset.measurements); self.assertNotEqual(generate_mesh(base)[0],generate_mesh(offset)[0])
    def test_chest_change_changes_derived_geometry(self):
        base=AvatarParameters({}); larger=base.with_measurements(chest=1200); self.assertNotEqual(generate_mesh(base)[0],generate_mesh(larger)[0])

if __name__=="__main__": unittest.main()
