"""FreeCAD-facing adapter from native PatternPiece documents into PatternIR.

PatternIR is the single solver-facing geometry boundary. This module is the
small adapter allowed to know how a document PatternPiece stores its geometry.
"""
from freecad_cloth.pattern.PatternGeometry import LineSegment, ParametricPattern, PolylineSegment
from freecad_cloth.pattern.PatternIR import PatternIR
from freecad_cloth.pattern.PatternModel import PatternPiece
from freecad_cloth.sewing.SeamGraph import SeamGraph


def _legacy_piece_model(piece):
    import ast

    try:
        points = [
            (float(value[0]), float(value[1]))
            for value in ast.literal_eval(str(getattr(piece, "SewingOutline", "")))
        ]
    except (ValueError, SyntaxError, TypeError, IndexError):
        points = []
    if len(points) < 3:
        width = float(getattr(piece, "Width", 0.0))
        height = float(getattr(piece, "Height", 0.0))
        points = [(0.0, 0.0), (width, 0.0), (width, height), (0.0, height)]
    return PatternPiece(
        str(getattr(piece, "Label", getattr(piece, "Name", "PatternPiece"))),
        points,
        id=str(getattr(piece, "PieceId", getattr(piece, "Name", "piece"))),
        seam_allowance=float(getattr(piece, "SeamAllowance", 0.0)),
        grainline_angle=float(getattr(piece, "GrainlineAngle", 0.0)),
    )


def resolve_piece_ir(piece, curve_samples=64):
    """Resolve one document PatternPiece through the authoritative PatternIR adapter."""
    sketch = getattr(piece, "Sketch", None)
    if sketch is not None and str(getattr(piece, "GeometryAuthority", "")) == "Sketcher":
        from freecad_cloth.common.SketchAuthority import _resolve_sketch_ir
        result = _resolve_sketch_ir(piece)
    else:
        model = _legacy_piece_model(piece)
        graph = SeamGraph()
        graph.add_piece(model)
        result = PatternIR.from_graph(graph).piece(model.id)
    result.validate()
    return result


def parametric_pattern_from_piece_ir(piece_ir):
    """Build a derived mesh pattern while retaining each IR boundary's identity."""
    segments = []
    for boundary in piece_ir.boundaries:
        points = tuple((float(sample[0]), float(sample[1])) for sample in boundary.samples)
        if len(points) < 2:
            raise ValueError("PatternIR boundary needs at least two 2D samples")
        if boundary.kind == "line" and len(points) == 2:
            segments.append(LineSegment(boundary.id, points[0], points[1]))
        else:
            segments.append(PolylineSegment(boundary.id, points))
    return ParametricPattern(segments)


def resolve_piece_pattern(piece, curve_samples=64):
    """Resolve a document PatternPiece to the derived mesh geometry through PatternIR."""
    return parametric_pattern_from_piece_ir(resolve_piece_ir(piece, curve_samples=curve_samples))
