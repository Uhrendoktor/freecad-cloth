# Copyright (C) 2026 FreeCAD Cloth contributors
"""FreeCAD-native Sketcher authority adapter for Cloth PatternPiece objects.

The PatternPiece remains the semantic/document object, but linked Sketcher
geometry is the editable geometric source. PatternIR preserves native curve
kind and connectivity. Sampled outlines are derived from Sketcher only for
FreeCAD display and shape construction; they are never a simulation fallback.
"""

from freecad_cloth.pattern.PatternIR import PieceIR
from freecad_cloth.pattern.PatternModel import PatternPiece


def _piece_model(obj: object) -> PatternPiece:
    """Build PatternIR metadata from a valid boundary seeded during creation."""
    import ast

    try:
        outline = [
            (float(point[0]), float(point[1]))
            for point in ast.literal_eval(str(getattr(obj, "DraftingBoundary", "")))
        ]
    except (ValueError, SyntaxError, TypeError, IndexError) as exc:
        msg = f"Sketcher PatternPiece {getattr(obj, 'PieceId', '')} has no valid seeded boundary"
        raise ValueError(msg) from exc
    if len(outline) < 3:
        msg = f"Sketcher PatternPiece {getattr(obj, 'PieceId', '')} needs at least three seed points"
        raise ValueError(msg)
    return PatternPiece(
        str(obj.Label),
        outline,
        id=str(obj.PieceId),
        seam_allowance=float(getattr(obj, "SeamAllowance", 0.0)),
        grainline_angle=float(getattr(obj, "GrainlineAngle", 0.0)),
    )


def _resolve_sketch_ir(obj: object) -> PieceIR:
    from freecad_cloth.pattern.PatternIR import PatternIR
    from freecad_cloth.sewing.SeamGraph import SeamGraph

    piece = _piece_model(obj)
    graph = SeamGraph()
    graph.add_piece(piece)
    return PatternIR.from_sketches(graph, {piece.id: obj.Sketch}, curve_samples=64).piece(piece.id)


def _sampled_outline(piece_ir: PieceIR) -> list[tuple[float, float]]:
    """Flatten ordered native boundary samples into a closed-outline polygon.

    Boundary samples include both endpoints; omit each edge's final endpoint
    because the following edge starts at that same vertex. Keeping every
    intermediate sample is essential for arcs and other curved Sketcher edges.
    """
    return [
        (float(sample[0]), float(sample[1]))
        for boundary in piece_ir.boundaries
        for sample in boundary.samples[:-1]
    ]


class SketchAuthorityProxy:
    """FeaturePython proxy that derives PatternPiece geometry from Sketcher."""

    Type = "ClothPatternPieceSketchAuthority"

    def execute(self, obj: object) -> None:
        """Recompute the FreeCAD object from its current source properties."""
        sketch = getattr(obj, "Sketch", None)
        if sketch is None or str(getattr(obj, "GeometryAuthority", "")) != "Sketcher":
            msg = "SketchAuthorityProxy requires a linked Sketcher-authoritative Sketch"
            raise ValueError(msg)

        piece_ir = _resolve_sketch_ir(obj)
        points = _sampled_outline(piece_ir)
        if len(points) < 3:
            msg = "authoritative Sketcher boundary needs at least three edges"
            raise ValueError(msg)

        obj.DraftingBoundary = repr(points)
        obj.SewingOutline = repr(points)
        obj.SewingBoundary = ",".join(boundary.id for boundary in piece_ir.boundaries)
        obj.Width = max(x for x, _ in points) - min(x for x, _ in points)
        obj.Height = max(y for _, y in points) - min(y for _, y in points)

        from freecad_cloth.pattern.PatternObjects import PatternPieceProxy

        obj.GeometryMode = "Custom"
        PatternPieceProxy().execute(obj)
        obj.GeometryMode = "Sketch"
        obj.GeometryAuthority = "Sketcher"

        if abs(float(getattr(obj, "SeamAllowance", 0.0))) <= 1e-12:
            try:
                import Part

                shape = sketch.Shape
                if not shape.isNull():
                    if shape.Wires:
                        obj.Shape = Part.Face(shape.Wires[0])
                    else:
                        obj.Shape = shape.copy()
            except (AttributeError, TypeError, ValueError, RuntimeError):
                pass


def attach(obj: object, sketch: object) -> object:
    """Attach ``sketch`` as the persistent geometry authority of ``obj``."""
    if "Sketch" not in obj.PropertiesList:
        obj.addProperty("App::PropertyLink", "Sketch", "Cloth")
    if "GeometryAuthority" not in obj.PropertiesList:
        obj.addProperty("App::PropertyEnumeration", "GeometryAuthority", "Cloth")
        obj.GeometryAuthority = ["PatternParameters", "Sketcher"]
    obj.Sketch = sketch
    obj.GeometryAuthority = "Sketcher"
    obj.GeometryMode = "Sketch"
    obj.Proxy = SketchAuthorityProxy()
    obj.touch()
    return obj
