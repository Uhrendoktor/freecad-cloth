"""FreeCAD-native Sketcher authority adapter for Cloth PatternPiece objects.

The PatternPiece remains the semantic/document object, but linked Sketcher
geometry is the editable geometric source. PatternIR preserves native curve
kind and connectivity; the legacy PatternPiece outline is only a derived
sampling used by older mesh/GUI paths until those consumers are migrated.
"""


def _piece_model(obj):
    from freecad_cloth.pattern.PatternModel import PatternPiece
    import ast
    try:
        outline = [(float(p[0]), float(p[1])) for p in ast.literal_eval(str(getattr(obj, "DraftingBoundary", "")))]
    except (ValueError, SyntaxError, TypeError, IndexError):
        outline = [(0.0, 0.0), (float(obj.Width), 0.0), (float(obj.Width), float(obj.Height)), (0.0, float(obj.Height))]
    return PatternPiece(
        str(obj.Label), outline,
        id=str(obj.PieceId),
        seam_allowance=float(getattr(obj, "SeamAllowance", 0.0)),
        grainline_angle=float(getattr(obj, "GrainlineAngle", 0.0)),
    )


def _resolve_sketch_ir(obj):
    from freecad_cloth.pattern.PatternIR import freecad_cloth.pattern.PatternIR
    from freecad_cloth.sewing.SeamGraph import freecad_cloth.sewing.SeamGraph
    piece = _piece_model(obj)
    graph = SeamGraph()
    graph.add_piece(piece)
    return PatternIR.from_sketches(graph, {piece.id: obj.Sketch}, curve_samples=64).piece(piece.id)


def _sampled_outline(piece_ir):
    return [(float(boundary.samples[0][0]), float(boundary.samples[0][1])) for boundary in piece_ir.boundaries]


class SketchAuthorityProxy:
    """FeaturePython proxy that derives PatternPiece geometry from Sketcher."""

    Type = "ClothPatternPieceSketchAuthority"

    def execute(self, obj):
        sketch = getattr(obj, "Sketch", None)
        if sketch is None or str(getattr(obj, "GeometryAuthority", "")) != "Sketcher":
            from freecad_cloth.pattern.PatternObjects import PatternPieceProxy
            return PatternPieceProxy().execute(obj)

        piece_ir = _resolve_sketch_ir(obj)
        points = _sampled_outline(piece_ir)
        if len(points) < 3:
            raise ValueError("authoritative Sketcher boundary needs at least three edges")

        # Keep the legacy line-sampled boundary as a derived compatibility
        # representation. Native curve identity remains in PatternIR and in
        # the Sketcher object itself.
        import ast
        obj.DraftingBoundary = repr(points)
        obj.SewingOutline = repr(points)
        obj.SewingBoundary = ",".join(boundary.id for boundary in piece_ir.boundaries)
        obj.Width = max(x for x, _ in points) - min(x for x, _ in points)
        obj.Height = max(y for _, y in points) - min(y for _, y in points)

        # Reuse the existing seam-allowance/Part feature implementation for
        # compatibility consumers, then restore the authoritative mode.
        from freecad_cloth.pattern.PatternObjects import PatternPieceProxy
        obj.GeometryMode = "Custom"
        PatternPieceProxy().execute(obj)
        obj.GeometryMode = "Sketch"
        obj.GeometryAuthority = "Sketcher"

        # With no seam allowance, expose the actual Sketcher topology instead
        # of a sampled polygon. For allowances, the existing deterministic
        # derived offset remains the compatibility shape.
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


def attach(obj, sketch):
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
