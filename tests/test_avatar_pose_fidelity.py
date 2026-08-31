import unittest

from AvatarModel import AvatarParameters, Pose, generate_mesh


class AvatarPoseFidelityTests(unittest.TestCase):
    def test_pose_angles_change_mesh_and_wrist_landmarks(self):
        standing = AvatarParameters(pose=Pose("standing", 12, 12, 0, 0))
        raised = AvatarParameters(pose=Pose("standing", -35, 35, 20, -20))
        self.assertNotEqual(generate_mesh(standing)[0], generate_mesh(raised)[0])
        wrist = {p.name: p.position for p in generate_mesh(raised)[2]}
        self.assertNotEqual(wrist["wrist_left"], wrist["wrist_right"])

    def test_sitting_preset_changes_knee_landmarks_and_round_trips(self):
        standing = AvatarParameters(pose=Pose("standing"))
        sitting = AvatarParameters(pose=Pose("sitting"))
        standing_landmarks = {p.name: p.position for p in generate_mesh(standing)[2]}
        sitting_landmarks = {p.name: p.position for p in generate_mesh(sitting)[2]}
        self.assertNotEqual(standing_landmarks["knee_left"], sitting_landmarks["knee_left"])
        self.assertEqual(AvatarParameters.from_json(sitting.to_json()), sitting)

    def test_pose_angle_limits_are_rejected(self):
        with self.assertRaises(ValueError):
            Pose("standing", 91).validate()
        with self.assertRaises(ValueError):
            Pose("standing", 12, 12, -91).validate()


if __name__ == "__main__":
    unittest.main()
