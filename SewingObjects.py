"""FreeCAD document objects for sewing operations.

The FreeCAD object layer derives seam geometry from the semantic sewing
outline stored on each PatternPiece.  When a native Shape exposes matching
edges, those edges are sampled by arc length so curved/non-linear geometry is
handled without changing the solver-facing seam contract.  Rectangle
Width/Height remains a backwards-compatible fallback for older documents.
"""
import ast
from math import atan2, degrees, hypot


def _outline_points(piece):
    """Return the ordered sewing boundary as 2D points."""
    for attr in ("SewingOutline", "DraftingBoundary"):
        raw = getattr(piece, attr, "")
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


def _native_edge(piece, edge):
    """Return a native Shape edge when it maps one-to-one to the outline."""
    shape = getattr(piece, "Shape", None)
    edges = getattr(shape, "Edges", None)
    if edges is None:
        return None
    try:
        index = int(edge)
        outline = _outline_points(piece)
        if 0 <= index < len(edges) and len(edges) == len(outline):
            return edges[index]
    except (TypeError, ValueError, IndexError):
        pass
    return None


def _edge_polyline(piece, edge, sample_count=64):
    """Return a local 2D polyline suitable for arc-length operations."""
    edge = int(edge)
    native = _native_edge(piece, edge)
    if native is not None:
        try:
            values = native.discretize(Number=max(2, int(sample_count)))
            points = [(float(p.x), float(p.y)) for p in values]
            if len(points) >= 2:
                return points
        except (AttributeError, TypeError, ValueError, RuntimeError):
            pass

    points = _outline_points(piece)
    if edge < 0 or edge >= len(points):
        raise ValueError(f"seam edge {edge} is outside the pattern boundary")
    return [points[edge], points[(edge + 1) % len(points)]]


def _polyline_length(points):
    return sum(hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:]))


def _sample_polyline(points, fraction):
    """Sample a polyline at normalized arc length."""
    if not points:
        raise ValueError("cannot sample an empty edge")
    if len(points) == 1:
        return points[0]
    fraction = min(1.0, max(0.0, float(fraction)))
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
    points = _edge_polyline(piece, edge)
    return _polyline_length(points)


def _seam_length(piece, seam, prefix):
    start = float(getattr(seam, "StartA" if prefix == "A" else "StartB"))
    end = float(getattr(seam, "EndA" if prefix == "A" else "EndB"))
    if not 0 <= start <= 1 or not 0 <= end <= 1 or start >= end:
        raise ValueError("seam parameters must be normalized with positive extent")
    return _edge_length(piece, int(getattr(seam, "EdgeA" if prefix == "A" else "EdgeB"))) * (end - start)


def _edge_points(piece, edge, start=0.0, end=1.0, z=0.2):
    """Return seam-range endpoints after the piece Placement is applied."""
    import FreeCAD as App
    points = _edge_polyline(piece, edge)
    p0 = _sample_polyline(points, start)
    p1 = _sample_polyline(points, end)
    local0 = App.Vector(p0[0], p0[1], z)
    local1 = App.Vector(p1[0], p1[1], z)
    placement = getattr(piece, "Placement", None)
    if placement is not None:
        return placement.multVec(local0), placement.multVec(local1)
    return local0, local1


def _edge_samples(piece, edge, start, end, count, z=0.2):
    """Return evenly arc-length-spaced points over a normalized edge range."""
    import FreeCAD as App
    if count < 2:
        raise ValueError("correspondence requires at least two samples")
    points = _edge_polyline(piece, edge)
    values = []
    for i in range(count):
        t = float(i) / float(count - 1)
        p = _sample_polyline(points, float(start) + (float(end) - float(start)) * t)
        value = App.Vector(p[0], p[1], z)
        placement = getattr(piece, "Placement", None)
        values.append(placement.multVec(value) if placement is not None else value)
    return values


def _alignment_placement(piece_a, piece_b, seam):
    """Return a Placement that moves B's seam onto A's seam endpoints."""
    import FreeCAD as App
    a0, a1 = _edge_points(piece_a, seam.EdgeA, seam.StartA, seam.EndA)
    b0, b1 = _edge_points(piece_b, seam.EdgeB, seam.StartB, seam.EndB)
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


def _seam_correspondence(piece_a, piece_b, seam, count, alignment="endpoints"):
    """Build deterministic A/B stitch points from the same semantic seam.

    ``endpoints`` pairs points by normalized position between the seam's two
    endpoints.  ``uniform`` uses the same normalized fractions but samples
    each native edge by arc length, which is important for curved edges.
    """
    if count < 2:
        raise ValueError("correspondence requires at least two samples")
    alignment = str(alignment or "endpoints")
    if alignment not in ("endpoints", "uniform"):
        raise ValueError(f"unsupported sewing alignment: {alignment}")

    if alignment == "endpoints":
        a0, a1 = _edge_points(piece_a, seam.EdgeA, seam.StartA, seam.EndA)
        b0, b1 = _edge_points(piece_b, seam.EdgeB, seam.StartB, seam.EndB)
        a_points = [a0 + (a1 - a0) * (i / float(count - 1)) for i in range(count)]
        b_points = [b0 + (b1 - b0) * (i / float(count - 1)) for i in range(count)]
    else:
        a_points = _edge_samples(piece_a, seam.EdgeA, seam.StartA, seam.EndA, count)
        b_points = _edge_samples(piece_b, seam.EdgeB, seam.StartB, seam.EndB, count)

    if bool(getattr(seam, "ReversedB", False)):
        b_points.reverse()
    return list(zip(a_points, b_points))


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
        pairs = _seam_correspondence(piece_a, piece_b, seam, obj.StitchCount, getattr(obj, "Alignment", "endpoints"))
        obj.AssemblyPlacementB = _alignment_placement(piece_a, piece_b, seam)
        obj.StitchPoints = []
        for pa, pb in pairs:
            obj.StitchPoints.append(f"{pa.x:.6f},{pa.y:.6f},{pa.z:.6f}|{pb.x:.6f},{pb.y:.6f},{pb.z:.6f}")
        a0, a1 = pairs[0][0], pairs[-1][0]
        b0, b1 = pairs[0][1], pairs[-1][1]
        obj.Shape = Part.makeCompound([Part.makePolygon([p for p, _ in pairs]), Part.makePolygon([p for _, p in pairs])])


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
    obj.setEditorMode("StitchCount", 1)
    obj.addProperty("App::PropertyStringList", "StitchPoints", "Stitching").StitchPoints = []
    obj.addProperty("App::PropertyString", "Status", "Validation").Status = "Incomplete"
    obj.setEditorMode("ReversedB", 1)
    obj.setEditorMode("Alignment", 1)
    obj.setEditorMode("StitchGroup", 1)
    obj.setEditorMode("AssemblyPlacementB", 1)
    obj.Proxy = SewingOperationProxy()
    obj.Proxy.execute(obj)
    return obj
