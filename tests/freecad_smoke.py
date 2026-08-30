"""Headless FreeCAD runtime smoke/regression test."""
import sys
from pathlib import Path
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import FreeCAD as App
import Part
from PatternCommands import create_pattern_piece, create_pattern_sketch
from PatternOCCT import native_offset_wire
from SimulationObjects import create_simulation_scene,reset_scene,set_avatar_collision_source,step_scene
from AvatarCommands import create_avatar, set_avatar_measurements, set_avatar_pose, set_avatar_skin_offset
from DrapeCommands import create_drape_target_from_selection
from SewingGui import correspondence_report

def main():
    import FreeCADGui as Gui
    import InitGui
    workbenches=(InitGui.ClothPatternWorkbench(),InitGui.ClothSimulationWorkbench(),InitGui.ClothSewingWorkbench())
    assert all(w.GetClassName()=="Gui::PythonWorkbench" for w in workbenches)
    assert [w.MenuText for w in workbenches]==["Cloth Pattern","Cloth Simulation","Cloth Sewing"]
    class CorrespondenceFixture:
        StartA=0.0; EndA=1.0; StartB=0.0; EndB=1.0; ReversedB=True
    assert correspondence_report(CorrespondenceFixture(),120,121,0.05).status=="reversed"
    doc=App.newDocument("ClothSmoke");create_pattern_piece();obj=doc.getObject("PatternPiece");assert obj is not None;assert obj.PieceId=="pattern-piece-1";assert obj.SewingBoundary=="bottom,right,top,left";assert obj.Shape.isValid();initial=obj.Shape.BoundBox.XLength;obj.Width=120;doc.recompute();assert obj.Shape.isValid() and obj.Shape.BoundBox.XLength!=initial and obj.PieceId=="pattern-piece-1"
    obj.Placement=App.Placement(App.Vector(15,20,0),App.Rotation(App.Vector(0,0,1),15));doc.recompute();assert obj.Placement.Base==App.Vector(15,20,0);assert abs(obj.Placement.Rotation.Angle-15.0)<1e-9
    Gui.Selection.clearSelection();Gui.Selection.addSelection(obj);sketch=create_pattern_sketch();assert obj.Sketch==sketch;assert obj.GeometryMode=="Sketch";assert obj.GeometryAuthority=="Sketcher";assert sketch.GeometryAuthority=="Sketcher";assert list(sketch.SemanticEdgeIds)==["pattern-piece-1:edge:%d"%i for i in range(4)];assert obj.Visibility is False and sketch.Visibility is True
    old_length=obj.Shape.BoundBox.XLength
    import Sketcher
    constraint_index=sketch.addConstraint(Sketcher.Constraint("Distance",0,120.0));sketch.setDatum(constraint_index,App.Units.Quantity("140 mm"));doc.recompute()
    assert obj.Shape.isValid() and obj.Shape.BoundBox.XLength!=old_length and abs(float(obj.Width)-140.0)<1e-9 and abs(float(obj.Height)-60.0)<1e-9
    wire=Part.makePolygon([App.Vector(0,0,0),App.Vector(100,0,0),App.Vector(100,60,0),App.Vector(0,60,0),App.Vector(0,0,0)]);offset=native_offset_wire(wire,10.0);assert offset.isValid();assert abs(offset.BoundBox.XLength-120.0)<1e-6;assert abs(offset.BoundBox.YLength-80.0)<1e-6
    scene=create_simulation_scene(doc);avatar_proxy=doc.getObject("AvatarCollision");humanoid=doc.getObject("HumanoidAvatar");assert scene.ParticleCount==80;assert scene.ClothPieces==[doc.getObject("DrapePanelA"),doc.getObject("DrapePanelB")];assert scene.AvatarProxy==avatar_proxy;assert avatar_proxy.SourceObject==humanoid;assert avatar_proxy.CollisionType=="MeshSurface";assert avatar_proxy.CollisionTriangleCount>0;assert humanoid.AvatarType=="ParametricHumanoid";assert list(scene.PinSelection)==["0","7","40","47"];assert len(scene.SeamSelection)==5;before=doc.getObject("DrapePanelA").Mesh.BoundBox.ZMin;step_scene(scene,20);assert scene.SimulatedTime>0 and scene.FiniteState;assert doc.getObject("DrapePanelA").Mesh.CountFacets>0;after=doc.getObject("DrapePanelA").Mesh.BoundBox.ZMin;assert before!=after
    body=doc.addObject("Part::Feature","HumanoidBody");body.Label="Fixture Humanoid Body";body.Shape=Part.makeBox(80,80,160,App.Vector(-40,-40,-80));doc.recompute();avatar=set_avatar_collision_source(scene,body,thickness=2.0,deflection=2.0);assert avatar.CollisionType=="MeshSurface";assert avatar.SourceObject==body;assert avatar.CollisionVertexCount>=8 and avatar.CollisionTriangleCount>=12
    Gui.Selection.clearSelection();Gui.Selection.addSelection(body);target=create_drape_target_from_selection(deflection=2.0,thickness=2.0);assert target.TargetType=="FreeCAD Geometry";assert target.SourceObject==body;assert target.CollisionTriangleCount>=12;assert target.SourceSignature
    reset_scene(scene);step_scene(scene,2);assert scene.FiniteState and scene.SimulatedTime>0
    scene.PinSelection=["0","not-an-index","79"];scene.SeamSelection=["7-8","bad-pair","39-40"];reset_scene(scene);assert scene.Steps==0 and scene.SimulatedTime==0.0 and scene.FiniteState;assert scene.ClothPieces==[doc.getObject("DrapePanelA"),doc.getObject("DrapePanelB")];assert scene.AvatarProxy==doc.getObject("AvatarCollision")
    App.closeDocument(doc.Name)
    avatar_doc=App.newDocument("AvatarSmoke"); mannequin=create_avatar(); assert mannequin.AvatarStatus=="Valid" and mannequin.Shape.isValid() and mannequin.Shape.Volume>0; original=mannequin.Shape.Volume; set_avatar_measurements(chest=1100); assert mannequin.Shape.Volume!=original; set_avatar_pose("sewing"); set_avatar_skin_offset(6.0); assert mannequin.PosePreset=="sewing" and abs(float(mannequin.SkinOffset)-6.0)<1e-9 and mannequin.CollisionProxy is not None; avatar_doc.recompute()
    with tempfile.TemporaryDirectory() as directory:
        path=str(Path(directory)/"avatar.FCStd"); avatar_doc.saveAs(path); App.closeDocument(avatar_doc.Name); reopened=App.openDocument(path); restored=reopened.getObject("ClothAvatar"); assert restored is not None and restored.AvatarStatus=="Valid"; assert restored.PosePreset=="sewing"; assert abs(float(restored.Chest)-1100.0)<1e-9; assert abs(float(restored.SkinOffset)-6.0)<1e-9; App.closeDocument(reopened.Name)
    print("FreeCAD workbench, Sketcher, sewing correspondence, drape target, humanoid drape, and parametric avatar smoke test passed")
if __name__=="__main__":
    main()
    import FreeCADGui as Gui
    Gui.exit()
