"""Regression tests for the target-neutral draping contract."""

import unittest

from DrapeTarget import DrapeTargetSpec, source_signature


class _Vec:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = x, y, z


class _Rotation:
    def __init__(self, angle=0.0):
        self.Angle = angle
        self.Axis = _Vec(0.0, 0.0, 1.0)


class _Placement:
    def __init__(self, x=0.0, y=0.0, z=0.0, angle=0.0):
        self.Base = _Vec(x, y, z)
        self.Rotation = _Rotation(angle)


class _Shape:
    def __init__(self, value):
        self.value = value

    def isNull(self):
        return False

    def hashCode(self):
        return self.value


class _Target:
    Name = "Chair"
    Label = "Chair target"
    Placement = _Placement()
    Shape = _Shape(1)


class DrapeTargetTests(unittest.TestCase):
    def test_target_spec_accepts_mannequin_and_geometry(self):
        DrapeTargetSpec("Mannequin", "HumanoidAvatar", 1.0, 2.0).validate()
        DrapeTargetSpec("FreeCAD Geometry", "Chair", 0.5, 1.5).validate()

    def test_target_spec_rejects_invalid_settings(self):
        invalid = [
            DrapeTargetSpec("Unknown", "Chair"),
            DrapeTargetSpec("FreeCAD Geometry", "", 1.0, 0.0),
            DrapeTargetSpec("FreeCAD Geometry", "Chair", 0.0, 0.0),
            DrapeTargetSpec("FreeCAD Geometry", "Chair", 1.0, -1.0),
        ]
        for spec in invalid:
            with self.subTest(spec=spec):
                with self.assertRaises(ValueError):
                    spec.validate()

    def test_source_signature_changes_for_geometry_placement_and_collision_settings(self):
        target = _Target()
        baseline = source_signature(target, 1.0, 2.0)

        target.Shape.value = 2
        self.assertNotEqual(source_signature(target, 1.0, 2.0), baseline)

        target.Placement = _Placement(x=10.0, y=-5.0, angle=15.0)
        self.assertNotEqual(source_signature(target, 1.0, 2.0), baseline)

        moved = source_signature(target, 1.0, 2.0)
        self.assertNotEqual(source_signature(target, 0.5, 2.0), moved)
        self.assertNotEqual(source_signature(target, 0.5, 4.0), source_signature(target, 0.5, 2.0))

    def test_source_signature_is_stable_for_unchanged_target(self):
        target = _Target()
        self.assertEqual(source_signature(target, 1.0, 2.0), source_signature(target, 1.0, 2.0))


if __name__ == "__main__":
    unittest.main()
