"""Headless FreeCAD runtime smoke/regression test."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import FreeCAD as App
import Part
from PatternCommands import create_pattern_piece
from PatternModel import Seam
from PatternObjects import add_seam
from PatternOCCT import native_offset_wire
from SimulationObjects import create_simulation_scene, reset_scene, set_avatar_collision_source, step_scene
from SewingObjects import add_sewing_operation


def main():
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

    second = create_pattern_piece()
    second.Label = "PatternPieceB"
    second.Placement = App.Placement(App.Vector(120, 0, 0), App.Rotation())
    doc.recompute()
    seam = Seam(str(obj.PieceId), 0, str(second.PieceId), 0, id="smoke-seam", alignment="uniform", stitch_group="smoke")
    seam_obj = add_seam(doc, seam)
    operation = add_sewing_operation(doc, seam_obj, obj, second)
    doc.recompute()
    assert operation.SewingType == "SewingOperation"
    assert operation.StitchCount == operation.Stitches
    assert operation.Alignment == "uniform"
    assert operation.StitchGroup == "smoke"
    assert len(operation.StitchPoints) == operation.Stitches

    wire = Part.makePolygon([App.Vector(0, 0, 0), App.Vector(100, 0, 0), App.Vector(100, 60, 0), App.Vector(0, 60, 0), App.Vector(0, 0, 0)])
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

    import tempfile
    save_path = str(Path(tempfile.gettempdir()) / "freecad_cloth_sewing_smoke.FCStd")
    doc.recompute(); doc.saveAs(save_path)
    App.closeDocument(doc.Name)
    loaded = App.openDocument(save_path)
    loaded.recompute()
    reloaded_op = next(o for o in loaded.Objects if getattr(o, "SewingType", "") == "SewingOperation")
    assert reloaded_op.Status in {"Valid", "Length mismatch"}
    assert reloaded_op.StitchCount == reloaded_op.Stitches
    assert len(reloaded_op.StitchPoints) == reloaded_op.Stitches
    assert reloaded_op.Seam is not None and reloaded_op.PieceA is not None and reloaded_op.PieceB is not None
    print("FreeCAD workbench, sewing lifecycle/save-reload, native OCCT adapter, placement and humanoid drape smoke test passed")


if __name__ == "__main__":
    main()
