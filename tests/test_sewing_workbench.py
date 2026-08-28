import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from SewingObjects import SewingOperationProxy, _edge_length, _seam_length

def test_rectangular_seam_lengths():
    piece=SimpleNamespace(Width=100.0,Height=60.0); seam=SimpleNamespace(EdgeA=0,StartA=0.0,EndA=1.0,EdgeB=1,StartB=0.0,EndB=0.5)
    assert _edge_length(piece,0)==100.0 and _edge_length(piece,1)==60.0; assert _seam_length(piece,seam,"A")==100.0; assert _seam_length(piece,seam,"B")==30.0

def test_proxy_validates_and_updates_shape():
    class Vector:
        def __init__(self,x,y,z=0.0): self.x,self.y,self.z=x,y,z
    class Shape: pass
    fake_freecad=SimpleNamespace(Vector=Vector); fake_part=SimpleNamespace(Shape=Shape,makeLine=lambda a,b:(a,b),makeCompound=lambda shapes:tuple(shapes)); oldf=sys.modules.get("FreeCAD"); oldp=sys.modules.get("Part"); sys.modules["FreeCAD"]=fake_freecad; sys.modules["Part"]=fake_part
    try:
        seam=SimpleNamespace(EdgeA=0,StartA=0.0,EndA=1.0,EdgeB=0,StartB=0.0,EndB=1.0,ReversedB=False); a=SimpleNamespace(Width=100.0,Height=60.0); b=SimpleNamespace(Width=100.2,Height=60.0)
        obj=SimpleNamespace(Seam=seam,PieceA=a,PieceB=b,Tolerance=0.5,Stitches=8,Status="Incomplete",LengthA=0,LengthB=0,LengthDifference=0,StitchCount=0,Shape=None)
        SewingOperationProxy().execute(obj); assert obj.Status=="Valid" and obj.LengthDifference==0.2 and obj.StitchCount==8 and obj.Shape
        obj.Tolerance=0.1; SewingOperationProxy().execute(obj); assert obj.Status=="Length mismatch"
    finally:
        if oldf is None: sys.modules.pop("FreeCAD",None)
        else: sys.modules["FreeCAD"]=oldf
        if oldp is None: sys.modules.pop("Part",None)
        else: sys.modules["Part"]=oldp
if __name__=="__main__": test_rectangular_seam_lengths(); test_proxy_validates_and_updates_shape(); print("Sewing workbench object tests passed")
