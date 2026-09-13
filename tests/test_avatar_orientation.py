import unittest

from freecad_cloth.avatar.HumanoidMesh import _map_makehuman_axes


class AvatarOrientationTests(unittest.TestCase):
    def test_makehuman_y_up_maps_to_freecad_z_up(self):
        # MakeHuman Y is height; Z is depth. The import must not put the body
        # on its side when converted to FreeCAD's Z-up coordinate system.
        mapped = _map_makehuman_axes(((1.0, 10.0, 2.0), (-1.0, 0.0, -3.0)))
        self.assertEqual(mapped[0], (1.0, 2.0, 1.0))
        self.assertEqual(mapped[1], (-1.0, -3.0, 0.0))
        self.assertGreater(mapped[0][2] - mapped[1][2], abs(mapped[0][1] - mapped[1][1]))


if __name__ == "__main__":
    unittest.main()
