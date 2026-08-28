"""FreeCAD document objects for the cloth pattern model."""
import ast
from PatternModel import PatternPiece, Seam


def _parse_points(value):
    if not value:
        return []
    try:
        return [(float(p[0]), float(p[1])) for p in ast.literal_eval(str(value))]
    except (ValueError, SyntaxError, TypeError, IndexError):
        raise ValueError("invalid pattern boundary")


def _rectangle_points(width, height):
    return [(0.0, 0.0), (float(width), 0.0), (float(width), float(height)), (0.0, float(height))]


def _is_rectangle(points, width, height):
    return len(points) == 4 and points == _rectangle_points(width, height)


def _boundary_shape(points, allowance=0.0):
    import FreeCAD as App
    import Part
    from PatternGeometry import LineSegment, ParametricPattern, seam_allowance_outline
    values = list(points)
    segments = [LineSegment(str(i), values[i], values[(i + 1) % len(values)]) for i in range(len(values))]
    pattern = ParametricPattern(segments)
    outline = values if float(allowance) == 0.0 else seam_allowance_outline(pattern, float(allowance))
    wire = Part.makePolygon([App.Vector(x, y, 0) for x, y in outline] + [App.Vector(outline[0][0], outline[0][1], 0)])
    return Part.Face(wire)


class PatternPieceProxy:
    """Recomputable native geometry for rectangular or custom pattern pieces."""
    Type = "ClothPatternPiece"

    def execute(self, obj):
        width = float(obj.Width)
        height = float(obj.Height)
        allowance = float(obj.SeamAllowance)
        if width <= 0 or height <= 0:
            raise ValueError("pattern piece dimensions must be positive")
        if allowance < 0:
            raise ValueError("seam allowance cannot be negative")
        mode = str(getattr(obj, "GeometryMode", "Rectangle"))
        if mode == "Custom":
            points = _parse_points(getattr(obj, "DraftingBoundary", ""))
            if len(points) < 3:
                raise ValueError("custom pattern outline needs at least three points")
            obj.Width = max(x for x, _ in points) - min(x for x, _ in points)
            obj.Height = max(y for _, y in points) - min(y for _, y in points)
        else:
            points = _rectangle_points(width, height)
            obj.GeometryMode = "Rectangle"
        obj.DraftingBoundary = repr(points)
        obj.SewingOutline = repr(points)
        rectangle = _is_rectangle(points, float(obj.Width), float(obj.Height))
        obj.SewingBoundary = ",".join(("bottom", "right", "top", "left")[i] if rectangle else f"edge:{i}" for i in range(len(points)))
        obj.Shape = _boundary_shape(points, allowance)


def add_pattern_piece(doc, piece: PatternPiece):
    """Create a recomputable native Part feature for a pattern piece."""
    piece.validate()
    width = max(p[0] for p in piece.outline) - min(p[0] for p in piece.outline)
    height = max(p[1] for p in piece.outline) - min(p[1] for p in piece.outline)
    obj = doc.addObject("Part::FeaturePython", piece.name)
    obj.Label = piece.name
    obj.addProperty("App::PropertyString", "PatternType", "Cloth").PatternType = "PatternPiece"
    obj.addProperty("App::PropertyString", "PieceId", "Cloth").PieceId = piece.id
    obj.addProperty("App::PropertyLength", "Width", "Parameters").Width = width
    obj.addProperty("App::PropertyLength", "Height", "Parameters").Height = height
    obj.addProperty("App::PropertyLength", "SeamAllowance", "Cloth").SeamAllowance = piece.seam_allowance
    obj.addProperty("App::PropertyAngle", "GrainlineAngle", "Cloth").GrainlineAngle = piece.grainline_angle
    obj.addProperty("App::PropertyEnumeration", "GeometryMode", "Cloth").GeometryMode = ["Rectangle", "Custom"]
    obj.GeometryMode = "Rectangle" if _is_rectangle(piece.outline, width, height) else "Custom"
    obj.addProperty("App::PropertyString", "DraftingBoundary", "Cloth").DraftingBoundary = repr(piece.outline)
    obj.addProperty("App::PropertyString", "SewingBoundary", "Cloth")
    obj.addProperty("App::PropertyString", "SewingOutline", "Cloth")
    proxy = PatternPieceProxy()
    obj.Proxy = proxy
    proxy.execute(obj)
    return obj


def add_seam(doc, seam: Seam):
    seam.validate()
    piece_a = next((o for o in doc.Objects if getattr(o, "PieceId", "") == seam.piece_a), None)
    piece_b = next((o for o in doc.Objects if getattr(o, "PieceId", "") == seam.piece_b), None)
    obj = doc.addObject("Part::FeaturePython", "Seam")
    obj.Label = f"{seam.piece_a}:edge:{seam.edge_a} ↔ {seam.piece_b}:edge:{seam.edge_b}"
    obj.addProperty("App::PropertyString", "SeamId", "Seam").SeamId = seam.id
    obj.addProperty("App::PropertyString", "PieceA", "Seam").PieceA = seam.piece_a
    obj.addProperty("App::PropertyInteger", "EdgeA", "Seam").EdgeA = seam.edge_a
    obj.addProperty("App::PropertyString", "PieceB", "Seam").PieceB = seam.piece_b
    obj.addProperty("App::PropertyInteger", "EdgeB", "Seam").EdgeB = seam.edge_b
    obj.addProperty("App::PropertyFloat", "StartA", "Seam").StartA = seam.start_a
    obj.addProperty("App::PropertyFloat", "EndA", "Seam").EndA = seam.end_a
    obj.addProperty("App::PropertyFloat", "StartB", "Seam").StartB = seam.start_b
    obj.addProperty("App::PropertyFloat", "EndB", "Seam").EndB = seam.end_b
    obj.addProperty("App::PropertyBool", "ReversedB", "Seam").ReversedB = seam.reversed_b
    if piece_a is not None and piece_b is not None:
        import FreeCAD as App
        import Part
        points_a, points_b = _parse_points(piece_a.SewingOutline), _parse_points(piece_b.SewingOutline)
        if seam.edge_a < len(points_a) and seam.edge_b < len(points_b):
            aa, ab = points_a[seam.edge_a], points_a[(seam.edge_a + 1) % len(points_a)]
            bb, bc = points_b[seam.edge_b], points_b[(seam.edge_b + 1) % len(points_b)]
            pa0 = App.Vector(aa[0] + (ab[0] - aa[0]) * seam.start_a, aa[1] + (ab[1] - aa[1]) * seam.start_a, 0.4)
            pa1 = App.Vector(aa[0] + (ab[0] - aa[0]) * seam.end_a, aa[1] + (ab[1] - aa[1]) * seam.end_a, 0.4)
            pb0 = App.Vector(bb[0] + (bc[0] - bb[0]) * seam.start_b, bb[1] + (bc[1] - bb[1]) * seam.start_b, 0.4)
            pb1 = App.Vector(bb[0] + (bc[0] - bb[0]) * seam.end_b, bb[1] + (bc[1] - bb[1]) * seam.end_b, 0.4)
            if getattr(piece_a, "Placement", None) is not None:
                pa0, pa1 = piece_a.Placement.multVec(pa0), piece_a.Placement.multVec(pa1)
            if getattr(piece_b, "Placement", None) is not None:
                pb0, pb1 = piece_b.Placement.multVec(pb0), piece_b.Placement.multVec(pb1)
            obj.Shape = Part.makeCompound([Part.makeLine(pa0, pa1), Part.makeLine(pb0, pb1)])
    return obj


def add_pattern_mesh(doc, mesh, name="ClothMesh"):
    """Create a native FreeCAD Mesh::Feature from a solver-neutral mesh."""
    import Mesh
    import FreeCAD as App
    native = Mesh.Mesh()
    for a, b, c in mesh.triangles:
        native.addFacet(App.Vector(mesh.vertices[a][0], mesh.vertices[a][1], 0.0), App.Vector(mesh.vertices[b][0], mesh.vertices[b][1], 0.0), App.Vector(mesh.vertices[c][0], mesh.vertices[c][1], 0.0))
    obj = doc.addObject("Mesh::Feature", name)
    obj.Label = name
    obj.Mesh = native
    obj.addProperty("App::PropertyString", "ClothMeshType", "Cloth").ClothMeshType = "PatternSurface"
    obj.addProperty("App::PropertyInteger", "VertexCount", "Cloth").VertexCount = len(mesh.vertices)
    obj.addProperty("App::PropertyInteger", "TriangleCount", "Cloth").TriangleCount = len(mesh.triangles)
    return obj
