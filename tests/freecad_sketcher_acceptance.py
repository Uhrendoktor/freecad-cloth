"""Canonical FreeCAD/Xvfb acceptance for native Sketcher pattern authoring."""
import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
import Part
import Sketcher


def _events():
    Gui.updateGui()
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    QtWidgets.QApplication.processEvents()


def _close_task():
    if Gui.Control.activeDialog():
        Gui.Control.closeDialog()
        _events()


def _activate(name, commands):
    Gui.activateWorkbench(name)
    _events()
    if Gui.activeWorkbench().name() != name:
        raise RuntimeError("failed to activate %s" % name)
    missing = [command for command in commands if command not in Gui.listCommands()]
    if missing:
        raise RuntimeError("commands are not registered: %s" % ",".join(missing))


def _pattern_pieces(doc):
    return [obj for obj in doc.Objects if getattr(obj, "PatternType", "") == "PatternPiece"]


def _constraint_type(sketch, index):
    return str(getattr(sketch.Constraints[index], "Type", ""))


def _make_curved_piece_sketch(piece, doc):
    """Use native Sketcher geometry as the actual PatternPiece geometry authority."""
    sketch = piece.Sketch
    if sketch is None:
        raise RuntimeError("PatternPiece did not create a native Sketcher sketch")
    sketch.clear()
    geometry = [
        Part.LineSegment(App.Vector(0, 0, 0), App.Vector(100, 0, 0)),
        Part.LineSegment(App.Vector(100, 0, 0), App.Vector(100, 50, 0)),
        Part.ArcOfCircle(Part.Circle(App.Vector(50, 50, 0), App.Vector(0, 0, 1), 50), 0, math.pi),
        Part.LineSegment(App.Vector(0, 50, 0), App.Vector(0, 0, 0)),
    ]
    sketch.addGeometry(geometry, False)
    sketch.SemanticEdgeIds = [f"{piece.PieceId}:edge:{i}" for i in range(4)]
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
    width_index = sketch.addConstraint(Sketcher.Constraint("Distance", 0, 100.0))
    sketch.renameConstraint(width_index, "PieceWidth")
    height_index = sketch.addConstraint(Sketcher.Constraint("Distance", 1, 50.0))
    sketch.renameConstraint(height_index, "PieceHeight")
    sketch.setExpression("Constraints[PieceHeight]", "Constraints[PieceWidth] / 2")
    doc.recompute()
    if sketch.Shape.isNull() or piece.Shape.isNull():
        raise RuntimeError("curved PatternPiece did not produce native geometry")
    if _constraint_type(sketch, width_index) != "Distance" or _constraint_type(sketch, height_index) != "Distance":
        raise RuntimeError("native dimensional constraints were not retained")
    if abs(float(sketch.getDatum(height_index)) - 50.0) > 1e-6:
        raise RuntimeError("named Sketcher expression did not evaluate to the expected height")
    return sketch, width_index, height_index


def _exercise_constraint_families(doc, reference_sketch):
    """Exercise native geometric constraints without introducing a second constraint system."""
    audit = doc.addObject("Sketcher::SketchObject", "SketchConstraintAudit")
    audit.Label = "Sketcher Constraint Audit"
    lines = [
        Part.LineSegment(App.Vector(0, 0, 0), App.Vector(40, 0, 0)),
        Part.LineSegment(App.Vector(0, 30, 0), App.Vector(40, 30, 0)),
        Part.LineSegment(App.Vector(20, -15, 0), App.Vector(20, 45, 0)),
        Part.Point(App.Vector(10, 0, 0)),
        Part.Point(App.Vector(30, 0, 0)),
    ]
    audit.addGeometry(lines, False)
    audit.toggleConstruction(2)
    if not bool(audit.GeometryFacadeList[2].Construction):
        raise RuntimeError("native construction geometry flag was not retained")

    equal_index = audit.addConstraint(Sketcher.Constraint("Equal", 0, 1))
    audit.addConstraint(Sketcher.Constraint("Horizontal", 0))
    audit.addConstraint(Sketcher.Constraint("Horizontal", 1))
    point_on_object_index = audit.addConstraint(Sketcher.Constraint("PointOnObject", 3, 1, 0))
    symmetric_index = audit.addConstraint(Sketcher.Constraint("Symmetric", 3, 1, 4, 1, 2, 1))
    for index, expected in ((equal_index, "Equal"), (point_on_object_index, "PointOnObject"), (symmetric_index, "Symmetric")):
        if _constraint_type(audit, index) != expected:
            raise RuntimeError("missing native %s constraint" % expected)

    geometry_count = len(audit.Geometry)
    audit.addExternal(reference_sketch.Name, "Edge1")
    if len(audit.Geometry) != geometry_count:
        raise RuntimeError("external geometry unexpectedly became owned sketch geometry")
    external = getattr(audit, "ExternalGeometry", ())
    if not external:
        raise RuntimeError("native external geometry reference was not persisted in the sketch")
    doc.recompute()
    return audit


def run_acceptance():
    doc = App.newDocument("NativeSketcherAcceptance")
    try:
        _activate("ClothPatternWorkbench", ["ClothPattern_CreatePieceWithSketch", "ClothPattern_EditSketch"])
        Gui.runCommand("ClothPattern_CreatePieceWithSketch", 0)
        Gui.runCommand("ClothPattern_CreatePieceWithSketch", 0)
        doc.recompute()
        pieces = _pattern_pieces(doc)
        if len(pieces) != 2:
            raise RuntimeError("public Pattern command did not create two PatternPiece objects")
        curved, mate = pieces
        curved.Placement.Base.x = -130
        mate.Placement.Base.x = 20
        curved_sketch, width_index, height_index = _make_curved_piece_sketch(curved, doc)
        reference = mate.Sketch
        if reference is None:
            raise RuntimeError("second PatternPiece has no native Sketcher source")
        _exercise_constraint_families(doc, reference)

        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(curved)
        Gui.runCommand("ClothPattern_EditSketch", 0)
        _events()
        if not Gui.activeDocument().getInEdit():
            raise RuntimeError("public Pattern Edit Sketch command did not enter native Sketcher")
        Gui.activeDocument().resetEdit()
        _events()

        _activate("ClothSewingWorkbench", ["ClothSewing_CreateSeam"])
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(curved, "Edge3")
        Gui.Selection.addSelection(mate, "Edge1")
        Gui.runCommand("ClothSewing_CreateSeam", 0)
        doc.recompute()
        seam = next((obj for obj in doc.Objects if getattr(obj, "SeamId", "")), None)
        if seam is None or str(seam.Status) != "Valid":
            raise RuntimeError("public Sewing command did not create a valid seam from native Sketch edges")
        original_piece_id = str(curved.PieceId)
        original_height = float(curved_sketch.getDatum(height_index))

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "native-sketcher-acceptance.FCStd")
            doc.saveAs(path)
            App.closeDocument(doc.Name)
            doc = None
            reloaded = App.openDocument(path)
            curved = next((obj for obj in reloaded.Objects if str(getattr(obj, "PieceId", "")) == original_piece_id), None)
            if curved is None or curved.Sketch is None:
                raise RuntimeError("PatternPiece native Sketcher source did not survive save/reload")
            sketch = curved.Sketch
            if str(curved.GeometryAuthority) != "Sketcher":
                raise RuntimeError("Sketcher authority flag did not survive save/reload")
            if str(sketch.GeometryAuthority) != "Sketcher":
                raise RuntimeError("Sketcher source authority did not survive save/reload")
            if str(sketch.getDatum(width_index)) == "":
                raise RuntimeError("named dimensional constraint did not survive save/reload")
            if abs(float(sketch.getDatum(height_index)) - original_height) > 1e-6:
                raise RuntimeError("named expression result did not survive save/reload")
            named_names = {str(c.Name) for c in sketch.Constraints if getattr(c, "Name", "")}
            if "PieceWidth" not in named_names or "PieceHeight" not in named_names:
                raise RuntimeError("named Sketcher dimensions did not survive save/reload")
            audit = reloaded.getObject("SketchConstraintAudit")
            if audit is None or not getattr(audit, "ExternalGeometry", ()):
                raise RuntimeError("external Sketcher reference did not survive save/reload")
            if not bool(audit.GeometryFacadeList[2].Construction):
                raise RuntimeError("construction geometry state did not survive save/reload")

            width_expression = sketch.getExpression("Constraints[PieceWidth]")
            height_expression = sketch.getExpression("Constraints[PieceHeight]")
            if width_expression not in (None, "") or height_expression in (None, ""):
                if width_expression in (None, ""):
                    raise RuntimeError("named width dimension lost its native expression state")
            sketch.setDatum(width_index, App.Units.Quantity("120 mm"))
            reloaded.recompute()
            if abs(float(sketch.getDatum(width_index)) - 120.0) > 1e-6:
                raise RuntimeError("native Sketcher dimensional edit did not apply")
            if abs(float(sketch.getDatum(height_index)) - 60.0) > 1e-6:
                raise RuntimeError("named Sketcher expression did not propagate after dimensional edit")
            changed_seam = next((obj for obj in reloaded.Objects if getattr(obj, "SeamId", "") == seam.SeamId), None)
            if changed_seam is None:
                raise RuntimeError("seam did not survive save/reload")
            if str(changed_seam.Status) == "Valid":
                raise RuntimeError("native Sketcher edit did not invalidate downstream seam")
            App.closeDocument(reloaded.Name)
            doc = None
        print("native Sketcher acceptance passed", flush=True)
    finally:
        _close_task()
        if doc is not None:
            try:
                App.closeDocument(doc.Name)
            except Exception:
                pass


if __name__ == "__main__":
    run_acceptance()
