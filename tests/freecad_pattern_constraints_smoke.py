"""FreeCAD/Xvfb acceptance for native Sketcher-driven Cloth patterns."""
import math
import os
import sys
import tempfile
import traceback

import FreeCAD as App
import FreeCADGui as Gui
import Part
import Sketcher

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

PROGRESS = "/workspace/artifacts/freecad-gui/pattern-constraints.log"
os.makedirs(os.path.dirname(PROGRESS), exist_ok=True)


def mark(message):
    with open(PROGRESS, "a", encoding="utf-8") as handle:
        handle.write(message + "\n")
        handle.flush()
    print("pattern-constraints: " + message, flush=True)


from freecad_cloth.pattern.PatternModel import PatternPiece, Seam
from freecad_cloth.pattern.PatternObjects import add_pattern_piece, add_seam
from freecad_cloth.pattern.PatternIR import PatternIR
from freecad_cloth.pattern.PatternGeometry import rectangle
from freecad_cloth.sewing.SeamGraph import SeamGraph


def _constraint_type(sketch, index):
    return str(sketch.Constraints[index].Type)


def _add_curved_sketch(piece):
    mark("building-curved-sketch")
    sketch = piece.Sketch
    sketch.clear()
    piece_id = str(piece.PieceId)
    geometry = [
        Part.LineSegment(App.Vector(0, 0, 0), App.Vector(100, 0, 0)),
        Part.LineSegment(App.Vector(100, 0, 0), App.Vector(100, 60, 0)),
        Part.ArcOfCircle(Part.Circle(App.Vector(50, 60, 0), App.Vector(0, 0, 1), 50), 0, math.pi),
        Part.LineSegment(App.Vector(0, 60, 0), App.Vector(0, 0, 0)),
    ]
    sketch.addGeometry(geometry, False)
    sketch.SemanticEdgeIds = [f"{piece_id}:edge:{i}" for i in range(4)]
    sketch.GeometryAuthority = "Sketcher"
    sketch.addConstraint([
        Sketcher.Constraint("Coincident", 0, 2, 1, 1),
        Sketcher.Constraint("Coincident", 1, 2, 2, 1),
        Sketcher.Constraint("Coincident", 2, 2, 3, 1),
        Sketcher.Constraint("Coincident", 3, 2, 0, 1),
        Sketcher.Constraint("Horizontal", 0),
        Sketcher.Constraint("Vertical", 1),
        Sketcher.Constraint("Vertical", 3),
        Sketcher.Constraint("Tangent", 1, 2, 2, 1),
    ])
    return sketch


def _exercise_reference_constraints(sketch, document):
    mark("reference-constraints")
    axis = sketch.addGeometry(Part.LineSegment(App.Vector(50, -20, 0), App.Vector(50, 100, 0)), True)
    left = sketch.addGeometry(Part.LineSegment(App.Vector(25, 20, 0), App.Vector(25, 40, 0)), True)
    right = sketch.addGeometry(Part.LineSegment(App.Vector(75, 20, 0), App.Vector(75, 40, 0)), True)
    equal = sketch.addConstraint(Sketcher.Constraint("Equal", left, right))
    point = sketch.addGeometry(Part.Point(App.Vector(50, 30, 0)), True)
    point_on_axis = sketch.addConstraint(Sketcher.Constraint("PointOnObject", point, 1, axis))
    symmetric = sketch.addConstraint(Sketcher.Constraint("Symmetric", left, 1, right, 1, axis))
    document.recompute()
    assert sketch.getAxisCount() >= 1
    assert _constraint_type(sketch, equal) == "Equal"
    assert _constraint_type(sketch, point_on_axis) == "PointOnObject"
    assert _constraint_type(sketch, symmetric) == "Symmetric"
    external = document.addObject("Part::Feature", "SketchReference")
    external.Shape = Part.makeLine(App.Vector(50, -20, 0), App.Vector(50, 100, 0))
    document.recompute()
    before = len(sketch.Geometry)
    result = sketch.addExternal(external.Name, "Edge1")
    assert result < 0
    assert sketch.getExternalGeometryCount() == 1
    assert len(sketch.Geometry) == before


def _exercise_dimension_expression(sketch, document):
    mark("dimension-expression")
    dimensional = sketch.addConstraint(Sketcher.Constraint("Distance", 0, 100.0))
    sketch.renameConstraint(dimensional, "Width")
    sketch.setExpression(f"Constraints[{dimensional}]", "120 mm")
    document.recompute()
    assert sketch.constraintHasExpression(dimensional)
    assert "120" in str(sketch.getExpression(f"Constraints[{dimensional}]"))
    assert abs(float(sketch.getDatum(dimensional)) - 120.0) < 1e-7
    return dimensional


def _assert_ir_preserves_native_curves(sketch, piece_id, document):
    mark("pattern-ir")
    piece = PatternPiece("Curved", [(0, 0), (100, 0), (100, 60), (0, 60)], id=piece_id)
    graph = SeamGraph()
    graph.add_piece(piece)
    ir = PatternIR.from_sketches(graph, {piece_id: sketch}, curve_samples=24)
    kinds = [boundary.kind for boundary in ir.pieces[0].boundaries]
    assert "arc" in kinds or "curve" in kinds
    assert len(ir.pieces[0].boundaries) == 4
    document.recompute()


def main(document=None):
    mark("start")
    doc = document or App.newDocument("PatternConstraintAcceptance")
    mark("document-ready")
    try:
        assert "ClothPattern_CreatePieceWithSketch" in Gui.listCommands()
        mark("creating-piece-command")
        Gui.runCommand("ClothPattern_CreatePieceWithSketch", 0)
        mark("piece-command-returned")
        doc.recompute()
        mark("initial-recompute-returned")
        piece = next((obj for obj in doc.Objects if getattr(obj, "PatternType", "") == "PatternPiece"), None)
        assert piece is not None and piece.Sketch is not None
        piece_name = piece.Name
        piece_id = str(piece.PieceId)
        sketch = piece.Sketch
        _add_curved_sketch(piece)
        doc.recompute()
        mark("curved-sketch-recompute-returned")
        assert list(sketch.SemanticEdgeIds) == [f"{piece_id}:edge:{i}" for i in range(4)]
        assert len(sketch.Geometry) == 4
        assert _constraint_type(sketch, 7) == "Tangent"
        _exercise_reference_constraints(sketch, doc)
        dimensional = _exercise_dimension_expression(sketch, doc)

        mark("creating-seam")
        piece2 = add_pattern_piece(doc, PatternPiece("Mate", rectangle(80, 50).sampled_outline(), id="pattern-piece-2"))
        doc.recompute()
        seam = add_seam(doc, Seam(piece_id, 0, str(piece2.PieceId), 0, id="AcceptanceSeam"))
        doc.recompute()
        assert seam.Status == "Valid"
        _assert_ir_preserves_native_curves(sketch, piece_id, doc)
        baseline_boundary = str(piece.SewingOutline)
        sketch.setDatum(dimensional, App.Units.Quantity("140 mm"))
        doc.recompute()
        assert str(piece.SewingOutline) != baseline_boundary
        assert str(seam.Status) in {"Changed reference", "Missing reference"}

        mark("save-reload")
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "pattern-constraints.FCStd")
            doc.recompute()
            doc.saveAs(path)
            App.closeDocument(doc.Name)
            reloaded = App.openDocument(path)
            restored = reloaded.getObject(piece_name)
            assert restored is not None
            restored_sketch = restored.Sketch
            assert restored_sketch is not None
            assert str(restored.GeometryAuthority) == "Sketcher"
            assert list(restored_sketch.SemanticEdgeIds) == [f"{restored.PieceId}:edge:{i}" for i in range(4)]
            restored_dimensional = next(i for i, constraint in enumerate(restored_sketch.Constraints) if str(constraint.Name) == "Width")
            assert restored_sketch.constraintHasExpression(restored_dimensional)
            assert abs(float(restored_sketch.getDatum(restored_dimensional)) - 140.0) < 1e-7
            assert restored_sketch.GeometryAuthority == "Sketcher"
            App.closeDocument(reloaded.Name)
            doc = None

        mark("passed")
    finally:
        if doc is not None and doc.Name in App.listDocuments():
            App.closeDocument(doc.Name)


if __name__ == "__main__":
    exit_code = 0
    try:
        main()
    except Exception:
        exit_code = 1
        mark("FAILED")
        traceback.print_exc()
    finally:
        try:
            for document in list(App.listDocuments().values()):
                try:
                    App.closeDocument(document.Name)
                except Exception:
                    pass
            window = Gui.getMainWindow()
            if window is not None:
                window.close()
            try:
                from PySide import QtWidgets
            except ImportError:
                from PySide2 import QtWidgets
            app = QtWidgets.QApplication.instance()
            if app is not None:
                app.quit()
        except Exception:
            pass
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(exit_code)
