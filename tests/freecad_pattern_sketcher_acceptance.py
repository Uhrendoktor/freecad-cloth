"""FreeCAD/Xvfb acceptance helpers for native Sketcher-backed Cloth Pattern authoring."""
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import FreeCAD as App
import FreeCADGui as Gui
import Part
import Sketcher
import InitGui


def _constraint_types(sketch):
    return {constraint.Type for constraint in sketch.Constraints}


def exercise_native_sketcher(doc, piece, sketch):
    """Exercise native Sketcher constraints/expressions on an existing PatternPiece."""
    semantic_ids = list(sketch.SemanticEdgeIds)
    assert sketch.TypeId == "Sketcher::SketchObject"
    assert sketch.GeometryAuthority == "Sketcher"
    assert piece.GeometryAuthority == "Sketcher"
    assert len(semantic_ids) == 4
    assert len(set(semantic_ids)) == 4

    arc = sketch.addGeometry(
        Part.ArcOfCircle(
            Part.Circle(App.Vector(50, 30, 0), App.Vector(0, 0, 1), 20),
            0.0,
            math.pi / 2.0,
        ),
        False,
    )
    tangent_line = sketch.addGeometry(
        Part.LineSegment(App.Vector(50, 50, 0), App.Vector(30, 50, 0)),
        True,
    )
    sketch.addConstraint(Sketcher.Constraint("Coincident", tangent_line, 1, arc, 2))
    sketch.addConstraint(Sketcher.Constraint("Tangent", arc, tangent_line))

    equal_line = sketch.addGeometry(
        Part.LineSegment(App.Vector(30, 60, 0), App.Vector(50, 60, 0)),
        True,
    )
    sketch.addConstraint(Sketcher.Constraint("Equal", tangent_line, equal_line))

    point_line = sketch.addGeometry(
        Part.LineSegment(App.Vector(40, 50, 0), App.Vector(40, 70, 0)),
        True,
    )
    sketch.addConstraint(Sketcher.Constraint("PointOnObject", point_line, 1, tangent_line))

    symmetric_a = sketch.addGeometry(
        Part.LineSegment(App.Vector(-20, 10, 0), App.Vector(-20, 20, 0)),
        True,
    )
    symmetric_b = sketch.addGeometry(
        Part.LineSegment(App.Vector(20, 10, 0), App.Vector(20, 20, 0)),
        True,
    )
    sketch.addConstraint(Sketcher.Constraint("Symmetric", symmetric_a, 1, symmetric_b, 1, -2))

    expression_line = sketch.addGeometry(
        Part.LineSegment(App.Vector(70, -20, 0), App.Vector(100, -20, 0)),
        True,
    )
    dimension = sketch.addConstraint(Sketcher.Constraint("Distance", expression_line, 30.0))
    sketch.renameConstraint(dimension, "PatternWidth")
    sketch.setExpression("Constraints.PatternWidth", "42 mm")
    doc.recompute()

    types = _constraint_types(sketch)
    for expected in ("Coincident", "Horizontal", "Vertical", "Tangent", "Equal", "PointOnObject", "Symmetric", "Distance"):
        assert expected in types, f"missing native Sketcher constraint: {expected}"
    assert abs(float(sketch.getDatum(dimension)) - 42.0) < 1e-7
    assert sketch.getExpression("Constraints.PatternWidth") == "42 mm"
    assert sketch.Geometry[arc].TypeId == "Part::GeomArcOfCircle"
    return semantic_ids


def main():
    """Run the isolated native Sketcher acceptance in a fresh FreeCAD document."""
    workbench = InitGui.ClothPatternWorkbench()
    Gui.activateWorkbench("Cloth Pattern")
    workbench.Initialize()
    assert "ClothPattern_CreateSketch" in workbench.commands
    assert "ClothPattern_CreatePieceWithSketch" in workbench.commands

    doc = App.newDocument("PatternSketcherAcceptance")
    try:
        from PatternCommands import create_pattern_piece_with_sketch
        piece = create_pattern_piece_with_sketch()
        sketch = piece.Sketch
        semantic_ids = exercise_native_sketcher(doc, piece, sketch)

        path = "/tmp/PatternSketcherAcceptance.FCStd"
        if os.path.exists(path):
            os.remove(path)
        doc.recompute()
        doc.saveAs(path)
        name = doc.Name
        App.closeDocument(name)
        reopened = App.openDocument(path)
        reopened.recompute()
        reloaded_piece = next(o for o in reopened.Objects if getattr(o, "PatternType", "") == "PatternPiece")
        reloaded_sketch = reloaded_piece.Sketch
        assert list(reloaded_sketch.SemanticEdgeIds) == semantic_ids
        assert reloaded_sketch.GeometryAuthority == "Sketcher"
        assert reloaded_sketch.getExpression("Constraints.PatternWidth") == "42 mm"
        assert any(c.Type == "Tangent" for c in reloaded_sketch.Constraints)
        assert any(c.Type == "Symmetric" for c in reloaded_sketch.Constraints)
        print("Native Sketcher Pattern acceptance passed: constraints, expression, curve, semantic IDs, save/reload")
    finally:
        if App.ActiveDocument is not None:
            Gui.Control.closeDialog()
            App.closeDocument(App.ActiveDocument.Name)


if __name__ == "__main__":
    main()
