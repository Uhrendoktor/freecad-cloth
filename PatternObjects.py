"""FreeCAD document objects for the cloth pattern model."""
from PatternModel import PatternPiece, Seam


class PatternPieceProxy:
    """Recomputable proxy for a rectangular parametric pattern piece."""

    Type = "ClothPatternPiece"

    def execute(self, obj):
        import FreeCAD as App
        import Part
        from PatternDrafting import default_points, parse_points, serialize_points, bounds, seam_allowance_preview

        width = float(obj.Width)
        height = float(obj.Height)
        allowance = float(obj.SeamAllowance)
        if width <= 0 or height <= 0:
            raise ValueError("pattern piece dimensions must be positive")
        if allowance < 0:
            raise ValueError("seam allowance cannot be negative")

        try:
            points = parse_points(obj.DraftingBoundary)
        except (ValueError, AttributeError):
            points = ()
        if not points:
            points = default_points(width, height)
        points = tuple(points)
        obj.DraftingBoundary = serialize_points(points)
        obj.SemanticSegments = "bottom,right,top,left"
        if not getattr(obj, "GrainlineMarker", ""):
            obj.GrainlineMarker = "centerline"
        if not getattr(obj, "NotchMarkers", ""):
            obj.NotchMarkers = "0,0;1,0;2,0;3,0"

        x0, y0, x1, y1 = bounds(points)
        obj.Width = max(0.001, x1 - x0)
        obj.Height = max(0.001, y1 - y0)
        obj.SewingBoundary = "bottom,right,top,left"
        obj.SewingOutline = repr(points)
        sewing = [App.Vector(x, y, 0) for x, y in points]
        sewing.append(sewing[0])
        if allowance:
            preview = seam_allowance_preview(points, allowance)
            outline = [App.Vector(x, y, 0) for x, y in preview]
            outline.append(outline[0])
        else:
            outline = sewing
        obj.Shape = Part.Face(Part.makePolygon(outline))


def add_pattern_piece(doc, piece: PatternPiece):
    """Create a recomputable native Part feature for a pattern piece."""
    piece.validate()
    obj = doc.addObject("Part::FeaturePython", piece.name)
    obj.Label = piece.name
    obj.addProperty("App::PropertyString", "PatternType", "Cloth").PatternType = "PatternPiece"
    obj.addProperty("App::PropertyString", "PieceId", "Cloth").PieceId = piece.id
    obj.addProperty("App::PropertyLength", "Width", "Parameters").Width = 100.0
    obj.addProperty("App::PropertyLength", "Height", "Parameters").Height = 60.0
    obj.addProperty("App::PropertyLength", "SeamAllowance", "Cloth").SeamAllowance = piece.seam_allowance
    obj.addProperty("App::PropertyAngle", "GrainlineAngle", "Cloth").GrainlineAngle = piece.grainline_angle
    obj.addProperty("App::PropertyString", "SewingBoundary", "Cloth")
    obj.addProperty("App::PropertyString", "SewingOutline", "Cloth")
    obj.addProperty("App::PropertyString", "DraftingBoundary", "Drafting")
    obj.addProperty("App::PropertyString", "SemanticSegments", "Drafting")
    obj.addProperty("App::PropertyString", "GrainlineMarker", "Marks")
    obj.addProperty("App::PropertyString", "NotchMarkers", "Marks")
    proxy = PatternPieceProxy()
    obj.Proxy = proxy
    proxy.execute(obj)
    return obj


def add_seam(doc, seam: Seam):
    seam.validate()
    obj = doc.addObject("App::FeaturePython", "Seam")
    obj.Label = f"{seam.piece_a}:{seam.edge_a} ↔ {seam.piece_b}:{seam.edge_b}"
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
    return obj


def add_pattern_mesh(doc, mesh, name="ClothMesh"):
    """Create a native FreeCAD Mesh::Feature from a solver-neutral mesh."""
    import Mesh
    import FreeCAD as App
    native = Mesh.Mesh()
    for a, b, c in mesh.triangles:
        native.addFacet(
            App.Vector(mesh.vertices[a][0], mesh.vertices[a][1], 0.0),
            App.Vector(mesh.vertices[b][0], mesh.vertices[b][1], 0.0),
            App.Vector(mesh.vertices[c][0], mesh.vertices[c][1], 0.0),
        )
    obj = doc.addObject("Mesh::Feature", name)
    obj.Label = name
    obj.Mesh = native
    obj.addProperty("App::PropertyString", "ClothMeshType", "Cloth").ClothMeshType = "PatternSurface"
    obj.addProperty("App::PropertyInteger", "VertexCount", "Cloth").VertexCount = len(mesh.vertices)
    obj.addProperty("App::PropertyInteger", "TriangleCount", "Cloth").TriangleCount = len(mesh.triangles)
    return obj
