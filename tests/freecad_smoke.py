"""Headless FreeCAD runtime smoke/regression test."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import FreeCAD as App
from PatternCommands import create_pattern_piece
from SimulationObjects import create_simulation_scene,reset_scene,step_scene

def main():
    import FreeCADGui as Gui
    import InitGui
    workbenches=(InitGui.ClothPatternWorkbench(),InitGui.ClothSimulationWorkbench(),InitGui.ClothSewingWorkbench())
    assert all(w.GetClassName()=="Gui::PythonWorkbench" for w in workbenches)
    assert [w.MenuText for w in workbenches]==["Cloth Pattern","Cloth Simulation","Cloth Sewing"]
    doc=App.newDocument("ClothSmoke");create_pattern_piece();obj=doc.getObject("PatternPiece");assert obj is not None;assert obj.PieceId=="pattern-piece-1";assert obj.SewingBoundary=="bottom,right,top,left";assert obj.Shape.isValid();initial=obj.Shape.BoundBox.XLength;obj.Width=120;doc.recompute();assert obj.Shape.isValid() and obj.Shape.BoundBox.XLength!=initial and obj.PieceId=="pattern-piece-1"
    scene=create_simulation_scene(doc);assert scene.ParticleCount==80;assert scene.ClothPieces==[doc.getObject("DrapePanelA"),doc.getObject("DrapePanelB")];assert scene.AvatarProxy==doc.getObject("AvatarCollision");assert list(scene.PinSelection)==["0","7","40","47"];assert len(scene.SeamSelection)==5;before=doc.getObject("DrapePanelA").Mesh.BoundBox.ZMin;step_scene(scene,20);assert scene.SimulatedTime>0 and scene.FiniteState;assert doc.getObject("DrapePanelA").Mesh.CountFacets>0;after=doc.getObject("DrapePanelA").Mesh.BoundBox.ZMin;assert before!=after
    scene.PinSelection=["0","not-an-index","79"];scene.SeamSelection=["7-8","bad-pair","39-40"];reset_scene(scene);assert scene.Steps==0 and scene.SimulatedTime==0.0 and scene.FiniteState;assert scene.ClothPieces==[doc.getObject("DrapePanelA"),doc.getObject("DrapePanelB")];assert scene.AvatarProxy==doc.getObject("AvatarCollision");print("FreeCAD workbench, document and drape smoke test passed")
if __name__=="__main__":main()
