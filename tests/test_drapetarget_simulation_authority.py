"""Regression coverage for target-authoritative Simulation integration."""

import unittest
from types import SimpleNamespace


class _FakeBackend:
    def __init__(self):
        self.step_calls = 0
        self.time = 0.0

    def step(self, *args, **kwargs):
        self.step_calls += 1

    def positions(self):
        return ((0.0, 0.0, 1.0),)

    def finite(self):
        return True


class DrapeTargetAuthorityTests(unittest.TestCase):
    def _source_and_target(self):
        from DrapeTarget import source_signature

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
            SourceSignature=repr(source_signature(source, 1.0, 0.0)),
            TargetStatus="ready", InvalidationReason="",
        )
        return source, target

    def test_simulation_prefers_persistent_drape_target_and_detects_invalidation(self):
        from DrapeTarget import target_status

        source, target = self._source_and_target()
        status = target_status(target)
        self.assertEqual(status["state"], "ready")

        source.Placement.Base.x = 10.0
        status = target_status(target)
        self.assertEqual(status["state"], "stale")
        self.assertTrue(status["stale"])
        self.assertIn("placement", status["reason"])

    def test_stale_target_collision_is_not_consumed_during_recompute(self):
        import SimulationObjects

        source, target = self._source_and_target()
        source.Placement.Base.x = 20.0
        scene = SimpleNamespace(DrapeTarget=target)
        self.assertIsNone(SimulationObjects._collision_for_scene(scene))
        self.assertEqual(target.TargetStatus, "stale")
        self.assertIn("source", target.InvalidationReason)

    def test_simulation_execute_is_safe_and_does_not_advance_when_target_is_stale(self):
        import SimulationObjects

        source, target = self._source_and_target()
        source.Placement.Base.x = 30.0
        proxy = SimulationObjects.SimulationProxy()
        backend = _FakeBackend()
        scene = SimpleNamespace(
            DrapeTarget=target, ClothPieces=(), Document=SimpleNamespace(Objects=()),
            StitchSamples=8, Steps=1, TimeStep=1.0 / 60.0, Iterations=8,
            GravityX=0.0, GravityY=0.0, GravityZ=-9810.0,
            CollisionX=0.0, CollisionY=0.0, CollisionZ=0.0, CollisionRadius=38.0,
            DrapePanels=(), SimulatedTime=0.0, ParticleCount=0, FiniteState=True,
        )
        proxy.backend = backend
        proxy.source_signature = SimulationObjects._simulation_source_signature(scene, ())
        proxy.last_steps = 0
        proxy.collision_surface = None

        proxy.execute(scene)

        self.assertEqual(backend.step_calls, 0)
        self.assertFalse(scene.FiniteState)
        self.assertEqual(scene.ParticleCount, 1)

    def test_public_step_run_gate_refuses_stale_target(self):
        import SimulationCommands

        source, target = self._source_and_target()
        source.Placement.Base.x = 40.0
        scene = SimpleNamespace(Steps=0)
        doc = SimpleNamespace(Objects=(target, scene))
        original = SimulationCommands._require_simulation
        try:
            SimulationCommands._require_simulation = lambda: (doc, scene)
            with self.assertRaisesRegex(RuntimeError, "Drape target changed"):
                SimulationCommands.simulate_selected(1)
            self.assertEqual(scene.Steps, 0)
        finally:
            SimulationCommands._require_simulation = original

    def test_target_contract_is_provider_neutral(self):
        from DrapeTarget import DrapeTargetSpec
        self.assertIn("Mannequin", DrapeTargetSpec.VALID_TYPES)
        self.assertIn("FreeCAD Geometry", DrapeTargetSpec.VALID_TYPES)


if __name__ == "__main__":
    unittest.main()
