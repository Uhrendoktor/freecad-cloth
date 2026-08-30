"""FreeCAD document objects for sewing operations.

The document layer derives sewing geometry from the stored pattern boundary
instead of assuming every pattern piece is a rectangle.  The semantic seam
remains the source of truth for ranges, orientation, and alignment.
"""
import ast
from math import hypot, atan2, degrees, radians, cos, sin


def _outline_points(piece):
    raw = getattr(piece, "SewingOutline", "")
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


def _edge_polyline(piece, edge):
    edge = int(edge)
    shape = getattr(piece, "Shape", None)
    edges = getattr(shape, "Edges", None)
    if edges is not None and 0 <= edge < len(edges):
        try:
            points = edges[edge].discretize(Number=32)
            if len(points) >= 2:
                return [(float(p.x), float(p.y)) for p in points]
        except (AttributeError, TypeError, ValueError, RuntimeError):
            pass
    points = _outline_points(piece)
    if edge < 0 or edge >= len(points):
        raise ValueError("seam edge is outside the pattern boundary")
    return [points[edge], points[(edge + 1) % len(points)]]


def _polyline_length(points):
    return sum(hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:]))


def _sample_polyline(points, fraction):
    fraction = max(0.0, min(1.0, float(fraction)))
    if len(points) == 1:
        return points[0]
    lengths = [0.0]
    for a, b in zip(points, points[1:]):
        lengths.append(lengths[-1] + hypot(b[0] - a[0], b[1] - a[1]))
    total = lengths[-1]
    if total <= 1e-12:
        return points[0]
    target = total * fraction
    for i in range(1, len(points)):
        if target <= lengths[i]:
            span = lengths[i] - lengths[i - 1]
            t = 0.0 if span <= 1e-12 else (target - lengths[i - 1]) / span
            a, b = points[i - 1], points[i]
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
    return points[-1]


def _edge_length(piece, edge):
    return _polyline_length(_edge_polyline(piece, edge))


def _seam_range(seam, prefix):
    start = float(getattr(seam, "StartA" if prefix == "A" else "StartB"))
    end = float(getattr(seam, "EndA" if prefix == "A" else "EndB"))
    if not 0.0 <= start < end <= 1.0:
        raise ValueError("seam parameters must be normalized with positive extent")
    return start, end


def _seam_length(piece, seam, prefix):
    start, end = _seam_range(seam, prefix)
    edge = int(getattr(seam, "EdgeA" if prefix == "A" else "EdgeB"))
    return _edge_length(piece, edge) * (end - start)


def _edge_points(piece, edge, start, end, z=0.2):
    import FreeCAD as App
    points = _edge_polyline(piece, edge)
    p0, p1 = _sample_polyline(points, start), _sample_polyline(points, end)
    v0, v1 = App.Vector(p0[0], p0[1], z), App.Vector(p1[0], p1[1], z)
    placement = getattr(piece, "Placement", None)
    if placement is not None:
        return placement.multVec(v0), placement.multVec(v1)
    return v0, v1


def _edge_samples(piece, edge, start, end, count, z=0.2):
    if count < 2:
        raise ValueError("sewing correspondence requires at least two samples")
    return [
        _edge_points(piece, edge, start + (end - start) * i / float(count - 1), start + (end - start) * i / float(count - 1), z)[0]
        for i in range(count)
    ]


def _seam_correspondence(piece_a, piece_b, seam, count, alignment):
    sa, ea = _seam_range(seam, "A")
    sb, eb = _seam_range(seam, "B")
    edge_a, edge_b = int(seam.EdgeA), int(seam.EdgeB)
    if alignment == "uniform":
        a = _edge_samples(piece_a, edge_a, sa, ea, count)
        b = _edge_samples(piece_b, edge_b, sb, eb, count)
    elif alignment == "endpoints":
        a0, a1 = _edge_points(piece_a, edge_a, sa, ea)
        b0, b1 = _edge_points(piece_b, edge_b, sb, eb)
        a = [a0 + (a1 - a0) * i / float(count - 1) for i in range(count)]
        b = [b0 + (b1 - b0) * i / float(count - 1) for i in range(count)]
    else:
        raise ValueError("unsupported sewing alignment: %s" % alignment)
    if bool(getattr(seam, "ReversedB", False)):
        b.reverse()
    return list(zip(a, b))


def _alignment_placement(piece_a, piece_b, seam):
    import FreeCAD as App
    a0, a1 = _edge_points(piece_a, int(seam.EdgeA), seam.StartA, seam.EndA)
    b0, b1 = _edge_points(piece_b, int(seam.EdgeB), seam.StartB, seam.EndB)
    if bool(getattr(seam, "ReversedB", False)):
        b0, b1 = b1, b0
    angle = degrees(atan2(a1.y - a0.y, a1.x - a0.x) - atan2(b1.y - b0.y, b1.x - b0.x))
    r = radians(angle)
    rx = b0.x * cos(r) - b0.y * sin(r)
    ry = b0.x * sin(r) + b0.y * cos(r)
    return App.Placement(App.Vector(a0.x - rx, a0.y - ry, a0.z - b0.z), App.Rotation(App.Vector(0, 0, 1), angle))


class SewingOperationProxy:
    Type = "ClothSewingOperation"

    def execute(self, obj):
        import Part
        seam = getattr(obj, "Seam", None)
        piece_a, piece_b = getattr(obj, "PieceA", None), getattr(obj, "PieceB", None)
        if seam is None or piece_a is None or piece_b is None:
            obj.Status = "Incomplete"
            obj.LengthA = obj.LengthB = obj.LengthDifference = 0.0
            obj.StitchCount = 0
            obj.Shape = Part.Shape()
            return
        if str(getattr(seam, "Status", "Valid")) != "Valid":
            obj.Status = "Invalid seam: " + str(getattr(seam, "Status", "Valid"))
            obj.LengthA = obj.LengthB = obj.LengthDifference = 0.0
            obj.StitchCount = 0
            obj.Shape = Part.Shape()
            return
        la, lb = _seam_length(piece_a, seam, "A"), _seam_length(piece_b, seam, "B")
        obj.LengthA, obj.LengthB = la, lb
        obj.LengthDifference = abs(la - lb)
        obj.StitchCount = max(2, int(obj.Stitches))
        obj.Status = "Valid" if obj.LengthDifference <= max(0.0, float(obj.Tolerance)) else "Length mismatch"
        alignment = str(getattr(seam, "Alignment", "endpoints"))
        if hasattr(obj, "Alignment"):
            obj.Alignment = alignment
        if hasattr(obj, "ReversedB"):
            obj.ReversedB = bool(getattr(seam, "ReversedB", False))
        pairs = _seam_correspondence(piece_a, piece_b, seam, obj.StitchCount, alignment)
        if hasattr(obj, "AssemblyPlacementB"):
            obj.AssemblyPlacementB = _alignment_placement(piece_a, piece_b, seam)
        obj.Shape = Part.makeCompound([Part.makeLine(a, b) for a, b in pairs])


def add_sewing_operation(doc, seam, piece_a, piece_b, name="SewingOperation"):
    obj = doc.addObject("Part::FeaturePython", name)
    obj.Label = name
    obj.addProperty("App::PropertyString", "SewingType", "Sewing").SewingType = "SewingOperation"
    obj.addProperty("App::PropertyLink", "Seam", "Sewing").Seam = seam
    obj.addProperty("App::PropertyLink", "PieceA", "Sewing").PieceA = piece_a
    obj.addProperty("App::PropertyLink", "PieceB", "Sewing").PieceB = piece_b
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
    obj.setEditorMode("StitchCount", 1)
    obj.addProperty("App::PropertyString", "Status", "Validation").Status = "Incomplete"
    obj.setEditorMode("Alignment", 1)
    obj.setEditorMode("ReversedB", 1)
    obj.setEditorMode("AssemblyPlacementB", 1)
    obj.Proxy = SewingOperationProxy()
    obj.Proxy.execute(obj)
    return obj
