"""Regression coverage for target-authoritative Simulation integration."""
import unittest
from types import SimpleNamespace


class DrapeTargetAuthorityTests(unittest.TestCase):
    def _target(self):
        from DrapeTarget import source_signature
        source = SimpleNamespace(
            Name="Body", Label="Body",
            Shape=SimpleNamespace(isNull=lambda: False, hashCode=lambda: 123),
            Placement=SimpleNamespace(Base=SimpleNamespace(x=0.0, y=0.0, z=0.0), Rotation=SimpleNamespace(Angle=0.0, Axis=SimpleNamespace(x=0.0, y=0.0, z=1.0))),
        )
        return source, SimpleNamespace(
            TargetType="FreeCAD Geometry", SourceObject=source, CollisionDeflection=1.0, CollisionThickness=0.0,
            Enabled=True, CollisionVertexCount=3, CollisionTriangleCount=1,
            SourceSignature=repr(source_signature(source, 1.0, 0.0)),
        )

    def test_persistent_target_detects_placement_invalidation(self):
        from DrapeTarget import target_status
        source, target = self._target()
        self.assertEqual(target_status(target)["state"], "ready")
        source.Placement.Base.x = 10.0
        status = target_status(target)
        self.assertEqual(status["state"], "stale")
        self.assertTrue(status["stale"])
        self.assertIn("placement", status["reason"])

    def test_simulation_guard_does_not_abort_recompute_on_stale_target(self):
        import DrapeTarget
        from SimulationObjects import SimulationProxy
        source, target = self._target()
        source.Placement.Base.x = 20.0
        scene = SimpleNamespace(DrapeTarget=target, FiniteState=True)
        DrapeTarget._install_simulation_guard()
        proxy = SimulationProxy()
        proxy.execute(scene)
        self.assertFalse(scene.FiniteState)

    def test_target_contract_is_provider_neutral(self):
        from DrapeTarget import DrapeTargetSpec
        self.assertIn("Mannequin", DrapeTargetSpec.VALID_TYPES)
        self.assertIn("FreeCAD Geometry", DrapeTargetSpec.VALID_TYPES)


if __name__ == "__main__":
    unittest.main()
