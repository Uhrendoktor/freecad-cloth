"""FreeCAD document objects for sewing operations.

Semantic seam data remains authoritative.  This adapter derives lengths,
correspondence, display geometry and assembly placement from the current
pattern geometry instead of maintaining a second sewing model.
"""
import ast
from math import atan2, degrees, hypot

from SeamGeometry import correspondence, outline_edge, polyline_length, sample_polyline


def _outline_points(piece):
    """Return the ordered sewing boundary as 2D points."""
    for attribute in ("SewingOutline", "DraftingBoundary"):
        raw = getattr(piece, attribute, "")
        if raw:
            try:
                values = ast.literal_eval(str(raw))
                points = [(float(p[0]), float(p[1])) for p in values]
                if len(points) >= 3:
                    return points
            except (ValueError, SyntaxError, TypeError, IndexError):
                pass
    width, height = float(piece.Width), float(piece.Height)
    return [(0.0, 0.0), (width, 0.0), (width, height), (0.0, height)]


def _edge_path(piece, edge):
    """Return a possibly curved, sampled edge from the document adapter."""
    raw = getattr(piece, "SewingEdgeSamples", "")
    if raw:
        try:
            data = ast.literal_eval(str(raw))
            values = data.get(str(int(edge)), data.get(int(edge))) if isinstance(data, dict) else None
            if values and len(values) >= 2:
                return [(float(p[0]), float(p[1])) for p in values]
        except (ValueError, SyntaxError, TypeError, IndexError, AttributeError):
            pass
    a, b = outline_edge(_outline_points(piece), int(edge))
    return [a, b]


def _edge_points(piece, edge, start=0.0, end=1.0, z=0.2, count=2):
    import FreeCAD as App
    samples = sample_polyline(_edge_path(piece, edge), float(start), float(end), max(2, int(count)))
    vectors = [App.Vector(x, y, z) for x, y in samples]
    placement = getattr(piece, "Placement", None)
    if placement is not None:
        vectors = [placement.multVec(v) for v in vectors]
    return tuple(vectors)


def _edge_length(piece, edge):
    return polyline_length(_edge_path(piece, int(edge)))


def _seam_length(piece, seam, prefix):
    start = float(getattr(seam, "StartA" if prefix == "A" else "StartB"))
    end = float(getattr(seam, "EndA" if prefix == "A" else "EndB"))
    if not 0 <= start <= 1 or not 0 <= end <= 1 or start >= end:
        raise ValueError("seam parameters must be normalized with positive extent")
    return _edge_length(piece, int(getattr(seam, "EdgeA" if prefix == "A" else "EdgeB"))) * (end - start)


def _alignment_placement(piece_a, piece_b, seam):
    """Return a Placement that moves B's seam onto A's seam endpoints."""
    import FreeCAD as App
    sa, ea = float(seam.StartA), float(seam.EndA)
    sb, eb = float(seam.StartB), float(seam.EndB)
    a = _edge_points(piece_a, seam.EdgeA, sa, ea, count=2)
    b = _edge_points(piece_b, seam.EdgeB, sb, eb, count=2)
    a0, a1 = a[0], a[-1]
    b0, b1 = b[-1], b[0] if bool(getattr(seam, "ReversedB", False)) else b[-1]
    if not bool(getattr(seam, "ReversedB", False)):
        b0, b1 = b[0], b[-1]
    avx, avy = a1.x - a0.x, a1.y - a0.y
    bvx, bvy = b1.x - b0.x, b1.y - b0.y
    if hypot(avx, avy) < 1e-12 or hypot(bvx, bvy) < 1e-12:
        return App.Placement()
    angle = degrees(atan2(avy, avx) - atan2(bvy, bvx))
    import math
    radians = math.radians(angle)
    rx = b0.x * math.cos(radians) - b0.y * math.sin(radians)
    ry = b0.x * math.sin(radians) + b0.y * math.cos(radians)
    translation = App.Vector(a0.x - rx, a0.y - ry, a0.z - b0.z)
    return App.Placement(translation, App.Rotation(App.Vector(0, 0, 1), angle))


class SewingOperationProxy:
    Type = "ClothSewingOperation"

    def execute(self, obj):
        import Part
        seam = getattr(obj, "Seam", None)
        piece_a = getattr(obj, "PieceA", None)
        piece_b = getattr(obj, "PieceB", None)
        if seam is None or piece_a is None or piece_b is None:
            obj.Status = "Incomplete"
            obj.LengthA = obj.LengthB = obj.LengthDifference = 0.0
            obj.StitchCount = 0
            obj.StitchPoints = []
            obj.Shape = Part.Shape()
            return
        la = _seam_length(piece_a, seam, "A")
        lb = _seam_length(piece_b, seam, "B")
        obj.LengthA, obj.LengthB = la, lb
        obj.LengthDifference = abs(la - lb)
        obj.StitchCount = max(2, int(obj.Stitches))
        obj.Status = "Valid" if obj.LengthDifference <= max(0.0, float(obj.Tolerance)) else "Length mismatch"
        if hasattr(obj, "ReversedB"):
            obj.ReversedB = bool(getattr(seam, "ReversedB", False))
        if hasattr(obj, "Alignment"):
            obj.Alignment = str(getattr(seam, "Alignment", "endpoints"))
        if hasattr(obj, "StitchGroup"):
            obj.StitchGroup = str(getattr(seam, "StitchGroup", "") or getattr(seam, "SeamId", "") or getattr(seam, "Name", ""))
        sa, ea = float(seam.StartA), float(seam.EndA)
        sb, eb = float(seam.StartB), float(seam.EndB)
        edge_a = _edge_path(piece_a, int(seam.EdgeA))
        edge_b = _edge_path(piece_b, int(seam.EdgeB))
        pairs = correspondence(edge_a, edge_b, sa, ea, sb, eb, max(2, int(obj.Stitches)), bool(getattr(seam, "ReversedB", False)))
        obj.AssemblyPlacementB = _alignment_placement(piece_a, piece_b, seam)
        obj.StitchPoints = []
        for pa, pb in pairs:
            import FreeCAD as App
            va, vb = App.Vector(pa[0], pa[1], 0.2), App.Vector(pb[0], pb[1], 0.2)
            if getattr(piece_a, "Placement", None) is not None: va = piece_a.Placement.multVec(va)
            if getattr(piece_b, "Placement", None) is not None: vb = piece_b.Placement.multVec(vb)
            obj.StitchPoints.append(f"{va.x:.6f},{va.y:.6f},{va.z:.6f}|{vb.x:.6f},{vb.y:.6f},{vb.z:.6f}")
        a0, a1 = _edge_points(piece_a, seam.EdgeA, sa, ea, count=2)[0], _edge_points(piece_a, seam.EdgeA, sa, ea, count=2)[-1]
        bpoints = _edge_points(piece_b, seam.EdgeB, sb, eb, count=2)
        b0, b1 = (bpoints[-1], bpoints[0]) if bool(getattr(seam, "ReversedB", False)) else (bpoints[0], bpoints[-1])
        obj.Shape = Part.makeCompound([Part.makeLine(a0, a1), Part.makeLine(b0, b1)])


def add_sewing_operation(doc, seam, piece_a, piece_b, name="SewingOperation"):
    obj = doc.addObject("Part::FeaturePython", name)
    obj.Label = name
    obj.addProperty("App::PropertyString", "SewingType", "Sewing").SewingType = "SewingOperation"
    obj.addProperty("App::PropertyLink", "Seam", "Sewing").Seam = seam
    obj.addProperty("App::PropertyLink", "PieceA", "Sewing").PieceA = piece_a
    obj.addProperty("App::PropertyLink", "PieceB", "Sewing").PieceB = piece_b
    obj.addProperty("App::PropertyString", "StitchGroup", "Sewing").StitchGroup = str(getattr(seam, "StitchGroup", "") or getattr(seam, "SeamId", "") or getattr(seam, "Name", ""))
    obj.addProperty("App::PropertyEnumeration", "Alignment", "Sewing").Alignment = ["endpoints", "uniform"]
    obj.Alignment = str(getattr(seam, "Alignment", "endpoints"))
    obj.addProperty("App::PropertyBool", "ReversedB", "Sewing").ReversedB = bool(getattr(seam, "ReversedB", False))
    obj.addProperty("App::PropertyPlacement", "AssemblyPlacementB", "Assembly").AssemblyPlacementB = piece_b.Placement
    obj.addProperty("App::PropertyLength", "Tolerance", "Validation").Tolerance = 0.5
    obj.addProperty("App::PropertyInteger", "Stitches", "Stitching").Stitches = 8
    obj.addProperty("App::PropertyLength", "LengthA", "Validation").LengthA = 0
    obj.addProperty("App::PropertyLength", "LengthB", "Validation").LengthB = 0
    obj.addProperty("App::PropertyLength", "LengthDifference", "Validation").LengthDifference = 0
    obj.addProperty("App::PropertyInteger", "StitchCount", "Stitching").StitchCount = 8
    obj.addProperty("App::PropertyStringList", "StitchPoints", "Stitching").StitchPoints = []
    obj.addProperty("App::PropertyString", "Status", "Validation").Status = "Incomplete"
    try:
        obj.setEditorMode("ReversedB", 1)
        obj.setEditorMode("Alignment", 1)
        obj.setEditorMode("StitchGroup", 1)
        obj.setEditorMode("StitchCount", 1)
        obj.setEditorMode("AssemblyPlacementB", 1)
    except AttributeError:
        pass
    obj.Proxy = SewingOperationProxy()
    obj.Proxy.execute(obj)
    return obj
