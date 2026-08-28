import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from SewingObjects import SewingOperationProxy,_edge_length,_seam_length

def test_rectangular_seam_lengths():
    piece=SimpleNamespace(Width=100.0,Height=60.0);seam=SimpleNamespace(EdgeA=0,StartA=0,EndA=1,EdgeB=1,StartB=0,EndB=.5)
    assert _edge_length(piece,0)==100 and _edge_length(piece,1)==60 and _seam_length(piece,seam,"A")==100 and _seam_length(piece,seam,"B")==30

def test_proxy_validation():
    class V:
        def __init__(self,x,y,z=0):self.x,self.y,self.z=x,y,z
    class S:pass
    oldf,oldp=sys.modules.get("FreeCAD"),sys.modules.get("Part");sys.modules["FreeCAD"]=SimpleNamespace(Vector=V);sys.modules["Part"]=SimpleNamespace(Shape=S,makeLine=lambda a,b:(a,b),makeCompound=lambda x:tuple(x))
    try:
        seam=SimpleNamespace(EdgeA=0,StartA=0,EndA=1,EdgeB=0,StartB=0,EndB=1,ReversedB=False);a=SimpleNamespace(Width=100,Height=60);b=SimpleNamespace(Width=100.2,Height=60);o=SimpleNamespace(Seam=seam,PieceA=a,PieceB=b,Tolerance=.5,Stitches=8,Status="Incomplete",LengthA=0,LengthB=0,LengthDifference=0,StitchCount=0,Shape=None);SewingOperationProxy().execute(o);assert o.Status=="Valid" and o.LengthDifference==.2 and o.Shape
    finally:
        if oldf is None:sys.modules.pop("FreeCAD",None)
        else:sys.modules["FreeCAD"]=oldf
        if oldp is None:sys.modules.pop("Part",None)
        else:sys.modules["Part"]=oldp
if __name__=="__main__":test_rectangular_seam_lengths();test_proxy_validation();print("sewing tests passed")
