"""FreeCAD document objects for sewing operations.

The sewing workbench stores construction metadata separately from the solver.
The object links existing PatternPiece and Seam features and provides a small,
recomputable visual preview of the paired seam edges.
"""


def _edge_length(piece, edge):
    """Return the baseline length for a rectangular pattern edge."""
    if edge in (0, 2):
        return float(piece.Width)
    if edge in (1, 3):
        return float(piece.Height)
    raise ValueError("seam edge must be between 0 and 3")


def _seam_length(piece, seam, prefix):
    start = float(getattr(seam, "StartA" if prefix == "A" else "StartB"))
    end = float(getattr(seam, "EndA" if prefix == "A" else "EndB"))
    if not 0.0 <= start <= 1.0 or not 0.0 <= end <= 1.0:
        raise ValueError("seam parameters must be between 0 and 1")
    return _edge_length(piece, int(getattr(seam, "EdgeA" if prefix == "A" else "EdgeB"))) * abs(end - start)


def _edge_points(piece, edge, start, end, z=0.2):
    """Return two FreeCAD vectors for a rectangular pattern edge segment."""
    import FreeCAD as App
    width = float(piece.Width)
    height = float(piece.Height)
    corners = {
        0: ((0.0, 0.0), (width, 0.0)),
        1: ((width, 0.0), (width, height)),
        2: ((width, height), (0.0, height)),
        3: ((0.0, height), (0.0, 0.0)),
    }
    try:
        a, b = corners[int(edge)]
    except KeyError:
        raise ValueError("seam edge must be between 0 and 3")
    return (
        App.Vector(a[0] + (b[0] - a[0]) * start, a[1] + (b[1] - a[1]) * start, z),
        App.Vector(a[0] + (b[0] - a[0]) * end, a[1] + (b[1] - a[1]) * end, z),
    )


class SewingOperationProxy:
    """Recomputable visual/validation proxy for a sewing operation."""

    Type = "ClothSewingOperation"

    def execute(self, obj):
        import Part

        seam = getattr(obj, "Seam", None)
        piece_a = getattr(obj, "PieceA", None)
        piece_b = getattr(obj, "PieceB", None)
        if seam is None or piece_a is None or piece_b is None:
            obj.Status = "Incomplete"
            obj.LengthA = 0.0
            obj.LengthB = 0.0
            obj.LengthDifference = 0.0
            obj.StitchCount = 0
            obj.Shape = Part.Shape()
            return

        length_a = _seam_length(piece_a, seam, "A")
        length_b = _seam_length(piece_b, seam, "B")
        difference = abs(length_a - length_b)
        tolerance = max(0.0, float(obj.Tolerance))
        obj.LengthA = length_a
        obj.LengthB = length_b
        obj.LengthDifference = difference
        obj.StitchCount = max(2, int(obj.Stitches))
        obj.Status = "Valid" if difference <= tolerance else "Length mismatch"

        start_a = float(seam.StartA)
        end_a = float(seam.EndA)
        start_b = float(seam.StartB)
        end_b = float(seam.EndB)
        if bool(seam.ReversedB):
            start_b, end_b = 1.0 - end_b, 1.0 - start_b
        a0, a1 = _edge_points(piece_a, seam.EdgeA, start_a, end_a)
        b0, b1 = _edge_points(piece_b, seam.EdgeB, start_b, end_b)
        obj.Shape = Part.makeCompound([Part.makeLine(a0, a1), Part.makeLine(b0, b1)])


def add_sewing_operation(doc, seam, piece_a, piece_b, name="SewingOperation"):
    """Create a native, recomputable sewing operation."""
    obj = doc.addObject("Part::FeaturePython", name)
    obj.Label = name
    obj.addProperty("App::PropertyString", "SewingType", "Sewing").SewingType = "SewingOperation"
    obj.addProperty("App::PropertyLink", "Seam", "Sewing").Seam = seam
    obj.addProperty("App::PropertyLink", "PieceA", "Sewing").PieceA = piece_a
    obj.addProperty("App::PropertyLink", "PieceB", "Sewing").PieceB = piece_b
    obj.addProperty("App::PropertyLength", "Tolerance", "Validation").Tolerance = 0.5
    obj.addProperty("App::PropertyInteger", "Stitches", "Stitching").Stitches = 8
    obj.addProperty("App::PropertyLength", "LengthA", "Validation").LengthA = 0.0
    obj.addProperty("App::PropertyLength", "LengthB", "Validation").LengthB = 0.0
    obj.addProperty("App::PropertyLength", "LengthDifference", "Validation").LengthDifference = 0.0
    obj.addProperty("App::PropertyInteger", "StitchCount", "Stitching").StitchCount = 8
    obj.addProperty("App::PropertyString", "Status", "Validation").Status = "Incomplete"
    obj.Proxy = SewingOperationProxy()
    obj.Proxy.execute(obj)
    return obj
