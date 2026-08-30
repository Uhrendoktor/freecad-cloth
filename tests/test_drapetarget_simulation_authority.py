"""Regression coverage for target-authoritative Simulation integration."""

import sys
import types
import unittest
from types import SimpleNamespace


class _FakeSurface:
    vertices = ((0.0, 0.0, 0.0),) * 3
    triangles = ((0, 1, 2),)


class _FakeBackend:
    def __init__(self):
        self.step_calls = 0
        self.time = 0.0

    def step(self, *args):
        self.step_calls += 1

    def positions(self):
        return ((0.0, 0.0, 0.0),)

    def finite(self):
        return True


class DrapeTargetAuthorityTests(unittest.TestCase):
    @staticmethod
    def _source():
        return SimpleNamespace(
            Name="Body",
            Label="Body",
            Shape=SimpleNamespace(isNull=lambda: False, hashCode=lambda: 123),
            Placement=SimpleNamespace(
                Base=SimpleNamespace(x=0.0, y=0.0, z=0.0),
                Rotation=SimpleNamespace(Angle=0.0, Axis=SimpleNamespace(x=0.0, y=0.0, z=1.0)),
            ),
        )

    def _ready_target(self):
        source = self._source()
        return source, SimpleNamespace(
            TargetType="FreeCAD Geometry", SourceObject=source,
            CollisionDeflection=1.0, CollisionThickness=0.0,
            Enabled=True, CollisionVertexCount=3, CollisionTriangleCount=1,
            SourceSignature=repr(("Body", "Body", ("Shape", 123), 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0)),
            TargetStatus="ready", InvalidationReason="",
        )

    def test_simulation_prefers_persistent_drape_target_over_avatar_proxy(self):
        from DrapeTarget import target_status

        source, target = self._ready_target()
        status = target_status(target)
        self.assertEqual(status["state"], "ready")

        source.Placement.Base.x = 10.0
        status = target_status(target)
        self.assertEqual(status["state"], "stale")
        self.assertTrue(status["stale"])

    def test_stale_target_collision_resolution_is_recompute_safe(self):
        from DrapeTarget import target_status
        from SimulationObjects import _collision_for_scene

        source, target = self._ready_target()
        source.Placement.Base.x = 10.0
        self.assertEqual(target_status(target)["state"], "stale")

        scene = SimpleNamespace(DrapeTarget=target)
        self.assertIsNone(_collision_for_scene(scene))
        self.assertEqual(target.TargetStatus, "stale")
        self.assertEqual(target.InvalidationReason, "source, placement, tessellation or collision thickness changed")

    def test_stale_target_blocks_solver_steps(self):
        from DrapeTarget import target_status
        from SimulationObjects import SimulationProxy, _simulation_source_signature

        source, target = self._ready_target()
        source.Placement.Base.x = 10.0
        self.assertEqual(target_status(target)["state"], "stale")

        scene = SimpleNamespace(
            ClothPieces=[], DrapePanels=[], DrapeTarget=target, Steps=3,
            StitchSamples=8, TimeStep=1.0, Iterations=1,
            GravityX=0.0, GravityY=0.0, GravityZ=-9.81,
            CollisionX=0.0, CollisionY=0.0, CollisionZ=0.0, CollisionRadius=0.0,
            SimulatedTime=0.0, ParticleCount=0, FiniteState=True,
        )
        proxy = SimulationProxy()
        proxy.backend = _FakeBackend()
        proxy.source_signature = _simulation_source_signature(scene, [])
        proxy.last_steps = 0

        proxy.execute(scene)

        self.assertEqual(proxy.backend.step_calls, 0)
        self.assertEqual(proxy.last_steps, 0)
        self.assertEqual(scene.Steps, 3)

    def test_simulation_command_preflight_blocks_stale_target(self):
        from DrapeTarget import target_status
        from SimulationCommands import _simulation_can_step

        source, target = self._ready_target()
        source.Placement.Base.x = 10.0
        self.assertEqual(target_status(target)["state"], "stale")
        doc = SimpleNamespace(Objects=[SimpleNamespace(TypeId="App::FeaturePython", Type="ClothSimulation"), target])
        fake_freecad = types.SimpleNamespace(ActiveDocument=doc)
        previous = sys.modules.get("FreeCAD")
        sys.modules["FreeCAD"] = fake_freecad
        try:
            self.assertFalse(_simulation_can_step())
        finally:
            if previous is None:
                sys.modules.pop("FreeCAD", None)
            else:
                sys.modules["FreeCAD"] = previous

    def test_target_contract_is_provider_neutral(self):
        from DrapeTarget import DrapeTargetSpec
        self.assertIn("Mannequin", DrapeTargetSpec.VALID_TYPES)
        self.assertIn("FreeCAD Geometry", DrapeTargetSpec.VALID_TYPES)


if __name__ == "__main__":
    unittest.main()
