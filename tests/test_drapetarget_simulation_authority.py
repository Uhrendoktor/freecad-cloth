"""Regression coverage for target-authoritative Simulation integration."""

import unittest
from types import SimpleNamespace


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
            TargetStatus="ready", InvalidationReason="",
        )
        return target, source

    def test_simulation_prefers_persistent_drape_target_over_avatar_proxy(self):
        from DrapeTarget import target_status
        target, source = self._target()
        status = target_status(target)
        self.assertEqual(status["state"], "ready")
        source.Placement.Base.x = 10.0
        status = target_status(target)
        self.assertEqual(status["state"], "stale")
        self.assertTrue(status["stale"])

    def test_stale_target_does_not_raise_during_execute(self):
        from DrapeTarget import _install_simulation_guard
        from SimulationObjects import SimulationProxy
        target, source = self._target()
        source.Placement.Base.x = 10.0
        obj = SimpleNamespace(DrapeTarget=target, FiniteState=True)
        proxy = SimulationProxy()
        proxy.collision_surface = object()
        _install_simulation_guard()
        proxy.execute(obj)
        self.assertFalse(obj.FiniteState)
        self.assertIsNone(proxy.collision_surface)
        self.assertEqual(target.TargetStatus, "stale")
        self.assertEqual(target.InvalidationReason, "source, placement, tessellation or collision thickness changed")

    def test_target_contract_is_provider_neutral(self):
        from DrapeTarget import DrapeTargetSpec
        self.assertIn("Mannequin", DrapeTargetSpec.VALID_TYPES)
        self.assertIn("FreeCAD Geometry", DrapeTargetSpec.VALID_TYPES)


if __name__ == "__main__":
    unittest.main()
