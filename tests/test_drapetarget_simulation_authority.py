"""Regression coverage for target-authoritative Simulation integration."""

import unittest
from types import SimpleNamespace


class _FakeSurface:
    vertices = ((0.0, 0.0, 0.0),) * 3
    triangles = ((0, 1, 2),)


class DrapeTargetAuthorityTests(unittest.TestCase):
    def _target(self):
        source = SimpleNamespace(
            Name="Body",
            Label="Body",
            Shape=SimpleNamespace(isNull=lambda: False, hashCode=lambda: 123),
            Placement=SimpleNamespace(
                Base=SimpleNamespace(x=0.0, y=0.0, z=0.0),
                Rotation=SimpleNamespace(Angle=0.0, Axis=SimpleNamespace(x=0.0, y=0.0, z=1.0)),
            ),
        )
        target = SimpleNamespace(
            TargetType="FreeCAD Geometry", SourceObject=source,
            CollisionDeflection=1.0, CollisionThickness=0.0,
            Enabled=True, CollisionVertexCount=3, CollisionTriangleCount=1,
            SourceSignature=repr(("Body", "Body", ("Shape", 123), 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0)),
        )
        return source, target

    def test_simulation_prefers_persistent_drape_target_over_avatar_proxy(self):
        from freecad_cloth.pattern.DrapeTarget import target_status

        source, target = self._target()
        status = target_status(target)
        self.assertEqual(status["state"], "ready")

        source.Placement.Base.x = 10.0
        status = target_status(target)
        self.assertEqual(status["state"], "stale")
        self.assertTrue(status["stale"])

    def test_stale_target_guard_blocks_proxy_recompute(self):
        from freecad_cloth.simulation.SimulationCommands import _drape_target_guard

        source, target = self._target()
        self.assertFalse(_drape_target_guard(target)["blocked"])
        source.Placement.Base.x = 10.0
        status = _drape_target_guard(target)
        self.assertTrue(status["blocked"])
        self.assertEqual(status["state"], "stale")
        self.assertIn("rebuild collision surface", status["message"])

    def test_target_contract_is_provider_neutral(self):
        from freecad_cloth.pattern.DrapeTarget import DrapeTargetSpec
        self.assertIn("Mannequin", DrapeTargetSpec.VALID_TYPES)
        self.assertIn("FreeCAD Geometry", DrapeTargetSpec.VALID_TYPES)


if __name__ == "__main__":
    unittest.main()
