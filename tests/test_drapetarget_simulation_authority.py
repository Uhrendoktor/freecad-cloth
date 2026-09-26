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
        from freecad_cloth.simulation.DrapeTarget import target_status
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
        from freecad_cloth.simulation.DrapeTarget import DrapeTargetSpec
        self.assertIn("Mannequin", DrapeTargetSpec.VALID_TYPES)
        self.assertIn("FreeCAD Geometry", DrapeTargetSpec.VALID_TYPES)


if __name__ == "__main__":
    unittest.main()


def test_fitting_simulation_target_propagation_and_staleness():
    try:
        import FreeCAD as App
        import Part
    except ModuleNotFoundError:
        return
    from freecad_cloth.avatar import FittingCommands
    from freecad_cloth.simulation.DrapeTarget import create_drape_target, target_status

    doc = App.newDocument("DrapeTargetSimulationPropagation")
    try:
        source = doc.addObject("Part::Feature", "TargetSource")
        source.Shape = Part.makeBox(20.0, 20.0, 20.0)
        target = create_drape_target(doc, source, "FreeCAD Geometry", 0.5, 0.0)
        piece = doc.addObject("Part::Feature", "PatternPiece")
        piece.Shape = Part.makeBox(5.0, 5.0, 1.0)
        piece.addProperty("App::PropertyString", "PatternType", "Pattern").PatternType = "PatternPiece"
        piece.addProperty("App::PropertyString", "PieceId", "Pattern").PieceId = "propagation-piece"
        fitting = FittingCommands.create_fitting_scene()
        fitting.DrapeTarget = target
        fitting.PatternPieces = [piece]
        doc.recompute()

        simulation = FittingCommands.create_simulation_from_fitting()
        assert simulation.DrapeTarget == target
        assert target_status(simulation.DrapeTarget)["state"] == "ready"

        source.Placement.Base.x += 15.0
        doc.recompute()
        assert target_status(simulation.DrapeTarget)["state"] == "stale"
    finally:
        if doc.Name in App.listDocuments():
            App.closeDocument(doc.Name)



if __name__ == "__main__":
    unittest.main()
