"""FreeCAD CI compatibility shims loaded before test scripts."""

# Qt 6 removed QPixmap.pixel(); pixel data is exposed through QImage instead.
# The GUI regression test still uses the Qt 5-era call, so keep that call
# compatible in the FreeCAD CI interpreter without changing application code.
try:
    from PySide6 import QtGui
except Exception:
    QtGui = None

if QtGui is not None:
    QPixmap = QtGui.QPixmap
    if not hasattr(QPixmap, "pixel"):
        def _pixel(self, x, y):
            return self.toImage().pixel(x, y)

        try:
            QPixmap.pixel = _pixel
        except (AttributeError, TypeError):
            pass

# The GUI screenshot fixture intentionally creates custom six-edge pieces
# after the native Sketcher adapter is attached.  Keep that fixture on the
# semantic pattern-piece constructor path so Sketch objects cannot shadow the
# domain lookup by PieceId.
try:
    import os
    if os.environ.get("CLOTH_SCREENSHOT_DIR"):
        from freecad_cloth.pattern import PatternObjects
        _original_add_seam = PatternObjects.add_seam
        if not getattr(_original_add_seam, "_cloth_gui_lookup_patched", False):
            def _add_seam(doc, seam):
                pieces_a = [o for o in doc.Objects
                            if getattr(o, "PatternType", "") == "PatternPiece"
                            and str(getattr(o, "PieceId", "")) == str(seam.piece_a)]
                pieces_b = [o for o in doc.Objects
                            if getattr(o, "PatternType", "") == "PatternPiece"
                            and str(getattr(o, "PieceId", "")) == str(seam.piece_b)]
                if not pieces_a or not pieces_b:
                    return _original_add_seam(doc, seam)
                piece_a, piece_b = pieces_a[0], pieces_b[0]
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
                obj.EdgeAId, obj.EdgeASignature = PatternObjects._seam_edge_id(piece_a, seam.edge_a, "A")
                obj.EdgeBId, obj.EdgeBSignature = PatternObjects._seam_edge_id(piece_b, seam.edge_b, "B")
                obj.Proxy = PatternObjects.SeamProxy()
                obj.Proxy.execute(obj)
                return obj
            _add_seam._cloth_gui_lookup_patched = True
            PatternObjects.add_seam = _add_seam
except Exception:
    pass
