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
        from freecad_cloth.simulation.DrapeTarget import source_signature

        target = SimpleNamespace(
            TargetType="FreeCAD Geometry",
            SourceObject=source,
            CollisionDeflection=1.0,
            CollisionThickness=0.0,
            Enabled=True,
            CollisionVertexCount=3,
            CollisionTriangleCount=1,
            SourceSignature=repr(source_signature(source, 1.0, 0.0)),
        )
        return source, target

    def test_simulation_prefers_persistent_drape_target_over_avatar_proxy(self):
        from freecad_cloth.simulation.DrapeTarget import target_status

        source, target = self._target()
        status = target_status(target)
        self.assertEqual(status["state"], "ready")
        source.Placement.Base.x = 10.0
        status = target_status(target)
        self.assertEqual(status["state"], "stale")
        self.assertTrue(status["stale"])

    def test_stale_target_guard_blocks_proxy_recompute(self):
        from freecad_cloth.simulation.SimulationCommands import _require_drape_target_ready

        source, target = self._target()
        document = SimpleNamespace(Objects=(target,))
        self.assertIs(_require_drape_target_ready(document), target)
        source.Placement.Base.x = 10.0
        with self.assertRaisesRegex(RuntimeError, "rebuild collision surface"):
            _require_drape_target_ready(document)

    def test_target_contract_is_provider_neutral(self):
        from freecad_cloth.simulation.DrapeTarget import DrapeTargetSpec

        self.assertIn("Mannequin", DrapeTargetSpec.VALID_TYPES)
        self.assertIn("FreeCAD Geometry", DrapeTargetSpec.VALID_TYPES)


if __name__ == "__main__":
    unittest.main()
