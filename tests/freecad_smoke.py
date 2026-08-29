"""Headless FreeCAD runtime smoke/regression test."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import FreeCAD as App
import Part
from PatternCommands import create_pattern_piece
from PatternOCCT import native_offset_wire
from SimulationObjects import create_simulation_scene, reset_scene, set_avatar_collision_source, step_scene
from SimulationQualityRuntimeV2 import create_quality_simulation_scene, apply_quality_preset


def main():
    import FreeCADGui as Gui
    import InitGui
    workbenches = (InitGui.ClothPatternWorkbench(), InitGui.ClothSimulationWorkbench(), InitGui.ClothSewingWorkbench())
    assert all(w.GetClassName() == "Gui::PythonWorkbench" for w in workbenches)
    assert [w.MenuText for w in workbenches] == ["Cloth Pattern", "Cloth Simulation", "Cloth Sewing"]

    doc = App.newDocument("ClothSmoke")
    create_pattern_piece()
    obj = doc.getObject("PatternPiece")
    assert obj is not None
    assert obj.PieceId == "pattern-piece-1"
    assert obj.SewingBoundary == "bottom,right,top,left"
    assert obj.Shape.isValid()
    initial = obj.Shape.BoundBox.XLength
    obj.Width = 120
    doc.recompute()
    assert obj.Shape.isValid() and obj.Shape.BoundBox.XLength != initial and obj.PieceId == "pattern-piece-1"
    obj.Placement = App.Placement(App.Vector(15, 20, 0), App.Rotation(App.Vector(0, 0, 1), 15))
    doc.recompute()
    assert obj.Placement.Base == App.Vector(15, 20, 0)
    assert abs(obj.Placement.Rotation.Angle - 15.0) < 1e-9

    wire = Part.makePolygon([
        App.Vector(0, 0, 0), App.Vector(100, 0, 0), App.Vector(100, 60, 0),
        App.Vector(0, 60, 0), App.Vector(0, 0, 0),
    ])
    offset = native_offset_wire(wire, 10.0)
    assert offset.isValid()
    assert abs(offset.BoundBox.XLength - 120.0) < 1e-6
    assert abs(offset.BoundBox.YLength - 80.0) < 1e-6

    scene = create_simulation_scene(doc)
    avatar_proxy = doc.getObject("AvatarCollision")
    humanoid = doc.getObject("HumanoidAvatar")
    assert scene.ParticleCount == 80
    assert scene.ClothPieces == [doc.getObject("DrapePanelA"), doc.getObject("DrapePanelB")]
    assert scene.AvatarProxy == avatar_proxy
    assert avatar_proxy.SourceObject == humanoid
    assert avatar_proxy.CollisionType == "MeshSurface"
    assert avatar_proxy.CollisionTriangleCount > 0
    assert humanoid.AvatarType == "ParametricHumanoid"
    assert list(scene.PinSelection) == ["0", "7", "40", "47"]
    assert len(scene.SeamSelection) == 5
    before = doc.getObject("DrapePanelA").Mesh.BoundBox.ZMin
    step_scene(scene, 20)
    assert scene.SimulatedTime > 0 and scene.FiniteState
    assert doc.getObject("DrapePanelA").Mesh.CountFacets > 0
    after = doc.getObject("DrapePanelA").Mesh.BoundBox.ZMin
    assert before != after

    body = doc.addObject("Part::Feature", "HumanoidBody")
    body.Label = "Fixture Humanoid Body"
    body.Shape = Part.makeBox(80, 80, 160, App.Vector(-40, -40, -80))
    doc.recompute()
    avatar = set_avatar_collision_source(scene, body, thickness=2.0, deflection=2.0)
    assert avatar.CollisionType == "MeshSurface"
    assert avatar.SourceObject == body
    assert avatar.CollisionVertexCount >= 8 and avatar.CollisionTriangleCount >= 12
    reset_scene(scene)
    step_scene(scene, 2)
    assert scene.FiniteState and scene.SimulatedTime > 0
    scene.PinSelection = ["0", "not-an-index", "79"]
    scene.SeamSelection = ["7-8", "bad-pair", "39-40"]
    reset_scene(scene)
    assert scene.Steps == 0 and scene.SimulatedTime == 0.0 and scene.FiniteState
    assert scene.ClothPieces == [doc.getObject("DrapePanelA"), doc.getObject("DrapePanelB")]
    assert scene.AvatarProxy == doc.getObject("AvatarCollision")

    quality_doc = App.newDocument("ClothQualitySmoke")
    quality_scene = create_quality_simulation_scene(quality_doc)
    quality_doc.recompute()
    assert quality_scene.QualityPreset == "Balanced"
    assert quality_scene.ParticleDistance == 4.0
    assert quality_scene.SolverIterations == 8
    assert quality_scene.SolverSubsteps == 1
    balanced_count = quality_scene.ParticleCount
    assert balanced_count > 0 and quality_scene.FiniteState

    apply_quality_preset(quality_scene, "Fast")
    quality_doc.recompute()
    fast_count = quality_scene.ParticleCount
    assert quality_scene.QualityPreset == "Fast"
    assert quality_scene.ParticleDistance == 8.0
    assert quality_scene.SolverIterations == 4
    assert quality_scene.SolverSubsteps == 1
    assert fast_count < balanced_count

    apply_quality_preset(quality_scene, "Final")
    quality_doc.recompute()
    final_count = quality_scene.ParticleCount
    assert quality_scene.QualityPreset == "Final"
    assert quality_scene.ParticleDistance == 2.0
    assert quality_scene.SolverIterations == 16
    assert quality_scene.SolverSubsteps == 2
    assert final_count > balanced_count

    quality_scene.FabricDensity = 300.0
    quality_scene.FabricThickness = 0.8
    quality_scene.FabricStretch = 0.04
    quality_scene.FabricShear = 0.03
    quality_scene.FabricBend = 0.02
    quality_scene.FabricFriction = 0.7
    quality_scene.AvatarSkinOffset = 2.0
    quality_doc.recompute()
    assert quality_scene.FiniteState
    assert quality_scene.ParticleCount == final_count
    assert quality_scene.SimulatedTime == 0.0

    quality_scene.Steps = 3
    quality_doc.recompute()
    assert quality_scene.SimulatedTime > 0.0 and quality_scene.FiniteState
    assert quality_scene.ParticleCount == final_count

    quality_path = str(Path(__file__).resolve().parent / "_quality_roundtrip.FCStd")
    quality_doc.saveAs(quality_path)
    App.closeDocument(quality_doc.Name)
    reloaded = App.openDocument(quality_path)
    reloaded_scene = next(obj for obj in reloaded.Objects if getattr(obj, "Type", "") == "ClothSimulation")
    assert reloaded_scene.QualityPreset == "Final"
    assert reloaded_scene.ParticleDistance == 2.0
    assert reloaded_scene.SolverIterations == 16
    assert reloaded_scene.SolverSubsteps == 2
    assert reloaded_scene.FabricDensity == 300.0
    assert reloaded_scene.FabricThickness == 0.8
    assert reloaded_scene.FabricStretch == 0.04
    assert reloaded_scene.FabricShear == 0.03
    assert reloaded_scene.FabricBend == 0.02
    assert reloaded_scene.FabricFriction == 0.7
    assert reloaded_scene.AvatarSkinOffset == 2.0
    reloaded.Steps = 4
    reloaded.recompute()
    assert reloaded_scene.FiniteState and reloaded_scene.SimulatedTime > 0.0
    App.closeDocument(reloaded.Name)
    Path(quality_path).unlink(missing_ok=True)
    App.closeDocument(doc.Name)
    print("FreeCAD workbench, native OCCT adapter, placement, humanoid drape and simulation-quality smoke test passed")


if __name__ == "__main__":
    main()
