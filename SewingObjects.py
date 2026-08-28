"""FreeCAD document objects for sewing operations.

The FreeCAD object layer derives seam geometry from the semantic sewing
outline stored on each PatternPiece. Rectangle Width/Height remains a
backwards-compatible fallback for older documents.
"""
import ast
from math import atan2, degrees, hypot


def _outline_points(piece):
    """Return the ordered sewing boundary as 2D points."""
    raw = getattr(piece, "SewingOutline", "")
    if raw:
        try:
            values = ast.literal_eval(str(raw))
            points = [(float(p[0]), float(p[1])) for p in values]
            if len(points) >= 3:
                return points
        except (ValueError, SyntaxError, TypeError, IndexError):
            pass
    raw = getattr(piece, "DraftingBoundary", "")
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


def _edge_points(piece, edge, start=0.0, end=1.0, z=0.2):
    import FreeCAD as App
    points = _outline_points(piece)
    edge = int(edge)
    if edge < 0 or edge >= len(points):
        raise ValueError(f"seam edge {edge} is outside the pattern boundary")
    a = points[edge]
    b = points[(edge + 1) % len(points)]
    p0 = App.Vector(a[0] + (b[0] - a[0]) * float(start), a[1] + (b[1] - a[1]) * float(start), z)
    p1 = App.Vector(a[0] + (b[0] - a[0]) * float(end), a[1] + (b[1] - a[1]) * float(end), z)
    placement = getattr(piece, "Placement", None)
    if placement is not None:
        return placement.multVec(p0), placement.multVec(p1)
    return p0, p1


def _edge_length(piece, edge):
    points = _outline_points(piece)
    edge = int(edge)
    if edge < 0 or edge >= len(points):
        raise ValueError(f"seam edge {edge} is outside the pattern boundary")
    a, b = points[edge], points[(edge + 1) % len(points)]
    return hypot(b[0] - a[0], b[1] - a[1])


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
    a0, a1 = _edge_points(piece_a, seam.EdgeA, sa, ea)
    b0, b1 = _edge_points(piece_b, seam.EdgeB, sb, eb)
    if bool(getattr(seam, "ReversedB", False)):
        b0, b1 = b1, b0
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
        sa, ea = float(seam.StartA), float(seam.EndA)
        sb, eb = float(seam.StartB), float(seam.EndB)
        if bool(getattr(seam, "ReversedB", False)):
            sb, eb = 1.0 - eb, 1.0 - sb
        a0, a1 = _edge_points(piece_a, seam.EdgeA, sa, ea)
        b0, b1 = _edge_points(piece_b, seam.EdgeB, sb, eb)
        obj.AssemblyPlacementB = _alignment_placement(piece_a, piece_b, seam)
        count = max(2, int(obj.Stitches))
        obj.StitchPoints = []
        for i in range(count):
            t = i / float(count - 1)
            pa = a0 + (a1 - a0) * t
            pb = b0 + (b1 - b0) * t
            obj.StitchPoints.append(f"{pa.x:.6f},{pa.y:.6f},{pa.z:.6f}|{pb.x:.6f},{pb.y:.6f},{pb.z:.6f}")
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
    obj.Alignment = "endpoints"
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
    obj.Proxy = SewingOperationProxy()
    obj.Proxy.execute(obj)
    return obj
