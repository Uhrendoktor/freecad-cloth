import unittest
from types import SimpleNamespace

from freecad_cloth.avatar.AvatarModel import AvatarParameters
from freecad_cloth.avatar.AvatarProvider import (
    AvatarProviderInfo,
    FreeCADGeometryAvatarProvider,
    ParametricAvatarProvider,
    provider_from_target,
)


class _Shape:
    Name = "Body"
    Label = "Imported Body"

    def __init__(self):
        self.Shape = self

    def isNull(self):
        return False

    def hashCode(self):
        return 42

    def tessellate(self, _deflection):
        vertices = tuple(SimpleNamespace(x=x, y=y, z=z) for x, y, z in (
            (0, 0, 0), (10, 0, 0), (0, 10, 0)))
        return vertices, ((0, 1, 2),)


class AvatarProviderTests(unittest.TestCase):
    def test_parametric_provider_is_deterministic_and_identified(self):
        provider = ParametricAvatarProvider(AvatarParameters())
        self.assertEqual(provider.info, AvatarProviderInfo(
            "parametric-mannequin", "Parametric human mannequin", "baseline"))
        self.assertEqual(provider.surface(), provider.collision_surface())
        self.assertGreater(len(provider.landmarks()), 5)

    def test_parametric_provider_keeps_authoritative_parameters(self):
        params = AvatarParameters()
        provider = ParametricAvatarProvider(params)
        self.assertEqual(provider.parameters(), params)

    def test_factory_selects_parametric_provider(self):
        provider = provider_from_target(None, "Mannequin", AvatarParameters())
        self.assertIsInstance(provider, ParametricAvatarProvider)

    def test_factory_selects_freecad_provider(self):
        source = _Shape()
        provider = FreeCADGeometryAvatarProvider(source)
        self.assertEqual(provider.info.provider_id, "freecad-geometry")
        self.assertIs(provider.source, source)
        self.assertIsNone(provider.parameters())
        self.assertEqual(provider.surface(), provider.collision_surface())

    def test_freecad_provider_rejects_invalid_tessellation(self):
        source = _Shape()
        with self.assertRaises(ValueError): FreeCADGeometryAvatarProvider(source, 0)
        with self.assertRaises(ValueError): FreeCADGeometryAvatarProvider(source, 1, -1)

    def test_factory_rejects_unknown_provider(self):
        with self.assertRaises(ValueError): provider_from_target(None, "Blender")


if __name__ == "__main__":
    unittest.main()
