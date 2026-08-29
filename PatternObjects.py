"""FreeCAD document objects for the cloth pattern model."""
import ast
from PatternModel import PatternPiece, Seam
from SeamReference import (
    ChangedEdgeReference,
    MissingEdgeReference,
    capture_edge_reference,
    semantic_edge_id,
    resolve_edge_reference,
)


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
    if float(allowance) == 0.0:
        outline = values
    elif _is_rectangle(values, max(p[0] for p in values) - min(p[0] for p in values), max(p[1] for p in values) - min(p[1] for p in values)):
        width = max(p[0] for p in values) - min(p[0] for p in values)
        height = max(p[1] for p in values) - min(p[1] for p in values)
        a = float(allowance)
        outline = [(-a, -a), (width + a, -a), (width + a, height + a), (-a, height + a)]
    else:
        segments = [LineSegment(str(i), values[i], values[(i + 1) % len(values)]) for i in range(len(values))]
        outline = seam_allowance_outline(ParametricPattern(segments), float(allowance))
    wire = Part.makePolygon([App.Vector(x, y, 0) for x, y in outline] + [App.Vector(outline[0][0], outline[0][1], 0)])
    return Part.Face(wire)


def _edge_records(piece):
    """Expose pattern edges through persistent semantic ids."""
    points = _parse_points(getattr(piece, "SewingOutline", ""))
    if len(points) < 2:
        return []
    piece_id = str(getattr(piece, "PieceId", ""))
    return [
        {
            "piece_id": piece_id,
            "id": semantic_edge_id(piece_id, index),
            "points": (points[index], points[(index + 1) % len(points)]),
            "ordinal": index,
        }
        for index in range(len(points))
    ]


def _seam_edge_id(piece, edge, prefix):
    """Return the semantic edge id and captured signature for a seam side."""
    records = _edge_records(piece)
    if isinstance(edge, int):
        if edge < 0 or edge >= len(records):
            raise MissingEdgeReference(f"seam edge {edge} is outside pattern piece {piece.PieceId}")
        record = records[edge]
        return record["id"], capture_edge_reference(piece.PieceId, record["id"], record["points"]).signature
    reference_id = str(edge)
    for record in records:
        if record["id"] == reference_id:
            return reference_id, capture_edge_reference(piece.PieceId, reference_id, record["points"]).signature
    raise MissingEdgeReference(f"semantic edge reference {reference_id} is missing from pattern piece {piece.PieceId}")


def _resolve_document_edge(piece, edge_id, signature):
    reference = capture_edge_reference(piece.PieceId, edge_id, ((0.0, 0.0), (1.0, 0.0)))
    reference = type(reference)(reference.piece_id, reference.edge_id, signature)
    return resolve_edge_reference(reference, _edge_records(piece))


class PatternPieceProxy:
    """Recomputable native geometry for rectangular or custom pattern pieces."""
    Type = "ClothPatternPiece"

    def execute(self, obj):
        width = float(obj.Width); height = float(obj.Height); allowance = float(obj.SeamAllowance)
        if width <= 0 or height <= 0: raise ValueError("pattern piece dimensions must be positive")
        if allowance < 0: raise ValueError("seam allowance cannot be negative")
        mode = str(getattr(obj, "GeometryMode", "Rectangle"))
        if mode == "Custom":
            points = _parse_points(getattr(obj, "DraftingBoundary", ""))
            if len(points) < 3: raise ValueError("custom pattern outline needs at least three points")
            obj.Width = max(x for x, _ in points) - min(x for x, _ in points)
            obj.Height = max(y for _, y in points) - min(y for _, y in points)
        else:
            points = _rectangle_points(width, height); obj.GeometryMode = "Rectangle"
        obj.DraftingBoundary = repr(points); obj.SewingOutline = repr(points)
        rectangle = _is_rectangle(points, float(obj.Width), float(obj.Height))
        obj.SewingBoundary = ",".join(("bottom", "right", "top", "left")[i] if rectangle else f"edge:{i}" for i in range(len(points)))
        obj.Shape = _boundary_shape(points, allowance)


def add_pattern_piece(doc, piece: PatternPiece):
    """Create a recomputable native Part feature for a pattern piece."""
    piece.validate()
    width = max(p[0] for p in piece.outline) - min(p[0] for p in piece.outline)
    height = max(p[1] for p in piece.outline) - min(p[1] for p in piece.outline)
    obj = doc.addObject("Part::FeaturePython", piece.name); obj.Label = piece.name
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
    obj.Proxy = PatternPieceProxy(); obj.Proxy.execute(obj)
    return obj


class SeamProxy:
    """Recompute semantic seam validity and visualization from pattern geometry."""
    Type = "ClothSeam"

    def execute(self, obj):
        import Part
        piece_a = getattr(obj, "PatternA", None)
        piece_b = getattr(obj, "PatternB", None)
        if piece_a is None or piece_b is None:
            obj.Status = "Missing reference"
            obj.Shape = Part.Shape()
            return
        try:
            a = _resolve_document_edge(piece_a, str(obj.EdgeAId), str(obj.EdgeASignature))
            b = _resolve_document_edge(piece_b, str(obj.EdgeBId), str(obj.EdgeBSignature))
        except MissingEdgeReference:
            obj.Status = "Missing reference"
            obj.Shape = Part.Shape()
            return
        except ChangedEdgeReference:
            obj.Status = "Changed reference"
            obj.Shape = Part.Shape()
            return
        obj.Status = "Valid"
        import FreeCAD as App
        aa, ab = a["points"]
        bb, bc = b["points"]
        pa0 = App.Vector(aa[0] + (ab[0] - aa[0]) * obj.StartA, aa[1] + (ab[1] - aa[1]) * obj.StartA, 0.4)
        pa1 = App.Vector(aa[0] + (ab[0] - aa[0]) * obj.EndA, aa[1] + (ab[1] - aa[1]) * obj.EndA, 0.4)
        pb0 = App.Vector(bb[0] + (bc[0] - bb[0]) * obj.StartB, bb[1] + (bc[1] - bb[1]) * obj.StartB, 0.4)
        pb1 = App.Vector(bb[0] + (bc[0] - bb[0]) * obj.EndB, bb[1] + (bc[1] - bb[1]) * obj.EndB, 0.4)
        if obj.ReversedB: pb0, pb1 = pb1, pb0
        if getattr(piece_a, "Placement", None) is not None: pa0, pa1 = piece_a.Placement.multVec(pa0), piece_a.Placement.multVec(pa1)
        if getattr(piece_b, "Placement", None) is not None: pb0, pb1 = piece_b.Placement.multVec(pb0), piece_b.Placement.multVec(pb1)
        obj.Shape = Part.makeCompound([Part.makeLine(pa0, pa1), Part.makeLine(pb0, pb1)])


def add_seam(doc, seam: Seam):
    seam.validate()
    piece_a = next((o for o in doc.Objects if getattr(o, "PieceId", "") == seam.piece_a), None)
    piece_b = next((o for o in doc.Objects if getattr(o, "PieceId", "") == seam.piece_b), None)
    obj = doc.addObject("Part::FeaturePython", "Seam")
    obj.Label = f"{seam.piece_a}:edge:{seam.edge_a} ↔ {seam.piece_b}:edge:{seam.edge_b}"
    obj.addProperty("App::PropertyString", "SeamId", "Seam").SeamId = seam.id
    obj.addProperty("App::PropertyString", "PieceA", "Seam").PieceA = seam.piece_a
    obj.addProperty("App::PropertyString", "EdgeAId", "Seam").EdgeAId = ""
    obj.addProperty("App::PropertyString", "EdgeASignature", "Seam").EdgeASignature = ""
    obj.addProperty("App::PropertyInteger", "EdgeA", "Compatibility").EdgeA = int(seam.edge_a) if isinstance(seam.edge_a, int) else -1
    obj.addProperty("App::PropertyString", "PieceB", "Seam").PieceB = seam.piece_b
    obj.addProperty("App::PropertyString", "EdgeBId", "Seam").EdgeBId = ""
    obj.addProperty("App::PropertyString", "EdgeBSignature", "Seam").EdgeBSignature = ""
    obj.addProperty("App::PropertyInteger", "EdgeB", "Compatibility").EdgeB = int(seam.edge_b) if isinstance(seam.edge_b, int) else -1
    obj.addProperty("App::PropertyLink", "PatternA", "Dependencies").PatternA = piece_a
    obj.addProperty("App::PropertyLink", "PatternB", "Dependencies").PatternB = piece_b
    obj.addProperty("App::PropertyFloat", "StartA", "Seam").StartA = seam.start_a
    obj.addProperty("App::PropertyFloat", "EndA", "Seam").EndA = seam.end_a
    obj.addProperty("App::PropertyFloat", "StartB", "Seam").StartB = seam.start_b
    obj.addProperty("App::PropertyFloat", "EndB", "Seam").EndB = seam.end_b
    obj.addProperty("App::PropertyBool", "ReversedB", "Seam").ReversedB = seam.reversed_b
    obj.addProperty("App::PropertyEnumeration", "Alignment", "Seam").Alignment = ["endpoints", "uniform"]
    obj.Alignment = seam.alignment
    obj.addProperty("App::PropertyString", "StitchGroup", "Seam").StitchGroup = seam.stitch_group or seam.id
    obj.addProperty("App::PropertyEnumeration", "Kind", "Seam").Kind = ["plain", "dart", "gather", "pleat", "hem", "fold", "closure"]
    obj.Kind = seam.kind
    obj.addProperty("App::PropertyString", "Status", "Validation").Status = "Incomplete"
    if piece_a is not None:
        obj.EdgeAId, obj.EdgeASignature = _seam_edge_id(piece_a, seam.edge_a, "A")
    if piece_b is not None:
        obj.EdgeBId, obj.EdgeBSignature = _seam_edge_id(piece_b, seam.edge_b, "B")
    obj.Proxy = SeamProxy()
    obj.Proxy.execute(obj)
    return obj


def add_pattern_mesh(doc, mesh, name="ClothMesh"):
    """Create a native FreeCAD Mesh::Feature from a solver-neutral mesh."""
    import Mesh, FreeCAD as App
    native = Mesh.Mesh()
    for a, b, c in mesh.triangles:
        native.addFacet(App.Vector(mesh.vertices[a][0], mesh.vertices[a][1], 0.0), App.Vector(mesh.vertices[b][0], mesh.vertices[b][1], 0.0), App.Vector(mesh.vertices[c][0], mesh.vertices[c][1], 0.0))
    obj = doc.addObject("Mesh::Feature", name); obj.Label = name; obj.Mesh = native
    obj.addProperty("App::PropertyString", "ClothMeshType", "Cloth").ClothMeshType = "PatternSurface"
    obj.addProperty("App::PropertyInteger", "VertexCount", "Cloth").VertexCount = len(mesh.vertices)
    obj.addProperty("App::PropertyInteger", "TriangleCount", "Cloth").TriangleCount = len(mesh.triangles)
    return obj
