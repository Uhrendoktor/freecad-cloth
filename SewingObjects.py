"""FreeCAD document objects for sewing operations."""
def _edge_length(piece, edge):
    if edge in (0,2): return float(piece.Width)
    if edge in (1,3): return float(piece.Height)
    raise ValueError("seam edge must be between 0 and 3")
def _seam_length(piece, seam, prefix):
    start=float(getattr(seam,"StartA" if prefix=="A" else "StartB")); end=float(getattr(seam,"EndA" if prefix=="A" else "EndB"))
    if not 0<=start<=1 or not 0<=end<=1: raise ValueError("seam parameters must be between 0 and 1")
    return _edge_length(piece,int(getattr(seam,"EdgeA" if prefix=="A" else "EdgeB")))*abs(end-start)
def _edge_points(piece, edge, start, end, z=0.2):
    import FreeCAD as App
    w,h=float(piece.Width),float(piece.Height); corners={0:((0,0),(w,0)),1:((w,0),(w,h)),2:((w,h),(0,h)),3:((0,h),(0,0))}
    try:a,b=corners[int(edge)]
    except KeyError:raise ValueError("seam edge must be between 0 and 3")
    p0=App.Vector(a[0]+(b[0]-a[0])*start,a[1]+(b[1]-a[1])*start,z); p1=App.Vector(a[0]+(b[0]-a[0])*end,a[1]+(b[1]-a[1])*end,z)
    placement=getattr(piece,"Placement",None)
    return (placement.multVec(p0),placement.multVec(p1)) if placement is not None else (p0,p1)
class SewingOperationProxy:
    Type="ClothSewingOperation"
    def execute(self,obj):
        import Part
        seam,piece_a,piece_b=getattr(obj,"Seam",None),getattr(obj,"PieceA",None),getattr(obj,"PieceB",None)
        if seam is None or piece_a is None or piece_b is None:
            obj.Status="Incomplete"; obj.LengthA=obj.LengthB=obj.LengthDifference=0.0; obj.StitchCount=0; obj.Shape=Part.Shape(); return
        la,lb=_seam_length(piece_a,seam,"A"),_seam_length(piece_b,seam,"B"); obj.LengthA=la; obj.LengthB=lb; obj.LengthDifference=abs(la-lb); obj.StitchCount=max(2,int(obj.Stitches)); obj.Status="Valid" if obj.LengthDifference<=max(0,float(obj.Tolerance)) else "Length mismatch"
        sa,ea,sb,eb=float(seam.StartA),float(seam.EndA),float(seam.StartB),float(seam.EndB)
        if bool(seam.ReversedB): sb,eb=1-eb,1-sb
        a0,a1=_edge_points(piece_a,seam.EdgeA,sa,ea); b0,b1=_edge_points(piece_b,seam.EdgeB,sb,eb); obj.Shape=Part.makeCompound([Part.makeLine(a0,a1),Part.makeLine(b0,b1)])
def add_sewing_operation(doc,seam,piece_a,piece_b,name="SewingOperation"):
    obj=doc.addObject("Part::FeaturePython",name); obj.Label=name
    obj.addProperty("App::PropertyString","SewingType","Sewing").SewingType="SewingOperation"; obj.addProperty("App::PropertyLink","Seam","Sewing").Seam=seam; obj.addProperty("App::PropertyLink","PieceA","Sewing").PieceA=piece_a; obj.addProperty("App::PropertyLink","PieceB","Sewing").PieceB=piece_b
    obj.addProperty("App::PropertyLength","Tolerance","Validation").Tolerance=0.5; obj.addProperty("App::PropertyInteger","Stitches","Stitching").Stitches=8; obj.addProperty("App::PropertyLength","LengthA","Validation").LengthA=0; obj.addProperty("App::PropertyLength","LengthB","Validation").LengthB=0; obj.addProperty("App::PropertyLength","LengthDifference","Validation").LengthDifference=0; obj.addProperty("App::PropertyInteger","StitchCount","Stitching").StitchCount=8; obj.addProperty("App::PropertyString","Status","Validation").Status="Incomplete"
    obj.Proxy=SewingOperationProxy(); obj.Proxy.execute(obj); return obj
