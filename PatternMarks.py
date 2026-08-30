"""Persistent manufacturing marks for the Cloth Pattern workbench."""
import ast


def _points(piece):
    try:
        return [(float(p[0]), float(p[1])) for p in ast.literal_eval(str(getattr(piece, "SewingOutline", "")))]
    except (ValueError, SyntaxError, TypeError, IndexError):
        return []


def _edge_points(piece, edge_id):
    from PatternObjects import _edge_records
    for record in _edge_records(piece):
        if record["id"] == str(edge_id): return record["points"]
    raise ValueError("pattern mark references a missing semantic edge")


def _point_on_edge(piece, edge_id, position):
    a, b = _edge_points(piece, edge_id); t = max(0.0, min(1.0, float(position)))
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


class PatternMarkProxy:
    Type = "ClothPatternMark"
    def execute(self, obj):
        import FreeCAD as App
        import Part
        piece = getattr(obj, "PatternPiece", None)
        if piece is None:
            obj.Status = "Missing pattern piece"; obj.Shape = Part.Shape(); return
        mark_type = str(getattr(obj, "MarkType", "Internal Mark"))
        try:
            if mark_type == "Grainline":
                points = _points(piece)
                if len(points) < 3: raise ValueError("pattern outline is missing")
                xs = [p[0] for p in points]; ys = [p[1] for p in points]
                cx = (min(xs) + max(xs)) * 0.5; cy = (min(ys) + max(ys)) * 0.5
                length = float(getattr(obj, "Length", max(max(xs)-min(xs), max(ys)-min(ys))*0.5))
                angle = float(getattr(obj, "Angle", getattr(piece, "GrainlineAngle", 0.0)))
                import math
                dx = math.cos(math.radians(angle))*length*0.5; dy = math.sin(math.radians(angle))*length*0.5
                p0 = App.Vector(cx-dx, cy-dy, 0.5); p1 = App.Vector(cx+dx, cy+dy, 0.5)
            else:
                p0x,p0y = _point_on_edge(piece,obj.EdgeId,obj.Position); a,b = _edge_points(piece,obj.EdgeId)
                import math
                vx,vy=b[0]-a[0],b[1]-a[1]; norm=math.hypot(vx,vy) or 1.0; nx,ny=-vy/norm,vx/norm; length=float(getattr(obj,"Length",10.0))
                if mark_type == "Notch":
                    p0=App.Vector(p0x-nx*length*0.5,p0y-ny*length*0.5,0.6); p1=App.Vector(p0x+nx*length*0.5,p0y+ny*length*0.5,0.6)
                else:
                    p0=App.Vector(p0x-vx/norm*length*0.5,p0y-vy/norm*length*0.5,0.6); p1=App.Vector(p0x+vx/norm*length*0.5,p0y+vy/norm*length*0.5,0.6)
            if getattr(piece,"Placement",None) is not None: p0,p1=piece.Placement.multVec(p0),piece.Placement.multVec(p1)
            obj.Shape=Part.makeLine(p0,p1); obj.Status="Valid"
        except (ValueError,TypeError,AttributeError,IndexError):
            obj.Shape=Part.Shape(); obj.Status="Changed reference"


def _next_name(doc, mark_type):
    prefix={"Notch":"Notch","Grainline":"Grainline","Internal Mark":"InternalMark","Fold":"Fold"}.get(mark_type,"PatternMark")
    index=1
    while doc.getObject("%s%d"%(prefix,index)) is not None: index+=1
    return "%s%d"%(prefix,index)


def add_pattern_mark(doc,piece,mark_type="Internal Mark",edge_id="",position=0.5,length=10.0,angle=0.0,label=""):
    valid_types=("Notch","Grainline","Internal Mark","Fold","Dart")
    if mark_type not in valid_types: raise ValueError("unsupported pattern mark type")
    if piece is None or getattr(piece,"PatternType","")!="PatternPiece": raise ValueError("pattern mark requires a PatternPiece")
    if mark_type!="Grainline": _edge_points(piece,edge_id)
    obj=doc.addObject("Part::FeaturePython",_next_name(doc,mark_type)); obj.Label=label or mark_type
    obj.addProperty("App::PropertyString","MarkType","Pattern Mark").MarkType=mark_type
    obj.addProperty("App::PropertyLink","PatternPiece","Pattern Mark").PatternPiece=piece
    obj.addProperty("App::PropertyString","PieceId","Pattern Mark").PieceId=str(piece.PieceId)
    obj.addProperty("App::PropertyString","EdgeId","Pattern Mark").EdgeId=str(edge_id)
    obj.addProperty("App::PropertyFloat","Position","Pattern Mark").Position=float(position)
    obj.addProperty("App::PropertyLength","Length","Pattern Mark").Length=float(length)
    obj.addProperty("App::PropertyAngle","Angle","Pattern Mark").Angle=float(angle)
    obj.addProperty("App::PropertyString","Status","Validation").Status="Incomplete"
    obj.Proxy=PatternMarkProxy(); obj.Proxy.execute(obj); return obj


def create_mark_from_selection(mark_type="Notch"):
    import FreeCAD as App
    import FreeCADGui as Gui
    doc=App.ActiveDocument or App.newDocument("ClothPattern")
    piece=next((o for o in Gui.Selection.getSelection() if getattr(o,"PatternType","")=="PatternPiece"),None)
    if piece is None: raise ValueError("select a pattern piece before adding a pattern mark")
    edge_id=""
    if mark_type!="Grainline":
        from PatternObjects import _edge_records
        for entry in Gui.Selection.getSelectionEx():
            if entry.Object is piece:
                for sub_name in entry.SubElementNames:
                    if str(sub_name).startswith("Edge"):
                        edge_number=int(str(sub_name)[4:])-1; records=_edge_records(piece)
                        if 0<=edge_number<len(records): edge_id=records[edge_number]["id"]; break
            if edge_id: break
        if not edge_id:
            records=_edge_records(piece)
            if not records: raise ValueError("pattern piece has no semantic edges")
            edge_id=records[0]["id"]
    obj=add_pattern_mark(doc,piece,mark_type,edge_id=edge_id,length=10.0,angle=float(getattr(piece,"GrainlineAngle",0.0))); doc.recompute(); return obj
