"""Canonical end-to-end FreeCAD garment acceptance for the Cloth workbenches."""
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
    missing = [command for command in commands if command not in Gui.listCommands()]
    if missing:
        raise RuntimeError("commands are not registered: %s" % ",".join(missing))


def _show_panel(panel, required):
    _close_task()
    Gui.Control.showDialog(panel)
    _events()
    widgets = [panel.form]
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    widgets.extend(panel.form.findChildren(QtWidgets.QWidget))
    text = " | ".join(
        str(getter())
        for widget in widgets
        for getter in [getattr(widget, "text", None)]
        if callable(getter)
    )
    missing = [item for item in required if item not in text]
    if missing:
        raise RuntimeError("task panel missing visible text: %s" % ",".join(missing))


def _find_pattern_pieces(doc):
    return [obj for obj in doc.Objects if getattr(obj, "PatternType", "") == "PatternPiece"]


def _make_curved(piece, doc):
    sketch = piece.Sketch
    piece_id = str(piece.PieceId)
    geometry = [
        Part.LineSegment(App.Vector(0, 0, 0), App.Vector(100, 0, 0)),
        Part.LineSegment(App.Vector(100, 0, 0), App.Vector(100, 50, 0)),
        Part.ArcOfCircle(Part.Circle(App.Vector(50, 50, 0), App.Vector(0, 0, 1), 50), 0, math.pi),
        Part.LineSegment(App.Vector(0, 50, 0), App.Vector(0, 0, 0)),
    ]
    sketch.Constraints = []
    sketch.Geometry = geometry
    sketch.SemanticEdgeIds = [f"{piece_id}:edge:{index}" for index in range(4)]
    sketch.GeometryAuthority = "Sketcher"
    sketch.addConstraint([
        Sketcher.Constraint("Coincident", 0, 2, 1, 1),
        Sketcher.Constraint("Coincident", 1, 2, 2, 1),
        Sketcher.Constraint("Coincident", 2, 2, 3, 1),
        Sketcher.Constraint("Coincident", 3, 2, 0, 1),
        Sketcher.Constraint("Horizontal", 0),
        Sketcher.Constraint("Vertical", 3),
        Sketcher.Constraint("Tangent", 1, 2, 2, 1),
    ])
    doc.recompute()
    if sketch.Shape.isNull() or piece.Shape.isNull():
        raise RuntimeError("curved pattern did not produce native geometry")
    return sketch


def run_acceptance():
    doc = App.newDocument("CanonicalGarmentAcceptance")
    try:
        _activate("ClothPatternWorkbench", ["ClothPattern_CreatePieceWithSketch", "ClothPattern_EditPiece"])
        Gui.runCommand("ClothPattern_CreatePieceWithSketch", 0)
        Gui.runCommand("ClothPattern_CreatePieceWithSketch", 0)
        doc.recompute()
        pieces = _find_pattern_pieces(doc)
        if len(pieces) != 2:
            raise RuntimeError("public Pattern command did not create two PatternPiece objects")
        curved, mate = pieces
        curved.Placement.Base.x = -120
        mate.Placement.Base.x = 20
        _make_curved(curved, doc)

        from freecad_cloth.pattern.PatternGui import PatternPieceTaskPanel
        _show_panel(PatternPieceTaskPanel(curved), ("Piece name", "Width", "Height", "Seam allowance", "Grainline angle"))
        _close_task()

        _activate("ClothSewingWorkbench", ["ClothSewing_CreateSeam", "ClothSewing_CreateOperation", "ClothSewing_Validate"])
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(curved, "Edge3")
        Gui.Selection.addSelection(mate, "Edge1")
        Gui.runCommand("ClothSewing_CreateSeam", 0)
        doc.recompute()
        seam = next((obj for obj in doc.Objects if getattr(obj, "SeamId", "")), None)
        if seam is None or str(seam.Status) != "Valid":
            raise RuntimeError("public Sewing command did not create a valid curved seam")
        Gui.Selection.clearSelection(); Gui.Selection.addSelection(seam)
        Gui.runCommand("ClothSewing_CreateOperation", 0)
        doc.recompute()
        operation = next((obj for obj in doc.Objects if getattr(obj, "SewingType", "") == "SewingOperation"), None)
        if operation is None or str(operation.Status) != "Valid":
            raise RuntimeError("public Sewing operation command did not create a valid operation")
        from freecad_cloth.sewing.SewingGui import SewingTaskPanel
        _show_panel(SewingTaskPanel(operation), ("Seam", "Alignment", "Validation tolerance", "Stitch samples", "Status"))
        _close_task()

        target_body = doc.addObject("Part::Feature", "AcceptanceTarget")
        target_body.Label = "Acceptance Target"
        target_body.Shape = Part.makeCylinder(35, 100, App.Vector(0, 0, -50))
        doc.recompute()

        _activate("ClothSimulationWorkbench", ["ClothSimulation_Create", "ClothSimulation_Step", "ClothSimulation_Reset", "ClothDrape_CreateTarget", "ClothDrape_RefreshTarget"])
        Gui.Selection.clearSelection()
        Gui.runCommand("ClothSimulation_Create", 0)
        doc.recompute()
        scene = doc.getObject("ClothSimulation")
        if scene is None:
            raise RuntimeError("public Simulation command did not create ClothSimulation")
        scene.ClothPieces = [curved, mate]
        doc.recompute()
        Gui.Selection.clearSelection(); Gui.Selection.addSelection(target_body)
        Gui.runCommand("ClothDrape_CreateTarget", 0)
        doc.recompute()
        target = doc.getObject("DrapeTarget")
        if target is None or target.SourceObject != target_body or scene.DrapeTarget != target:
            raise RuntimeError("public DrapeTarget command did not persist CAD target")
        from freecad_cloth.simulation.SimulationQualityGui import SimulationQualityTaskPanel
        _show_panel(SimulationQualityTaskPanel(scene), ("Preset", "Particle distance", "Density", "Avatar skin offset", "Simulation steps", "Step", "Run 30", "Reset"))
        _close_task()
        Gui.Selection.clearSelection(); Gui.Selection.addSelection(scene)
        Gui.runCommand("ClothSimulation_Step", 0)
        doc.recompute()
        if int(scene.Steps) < 1 or not bool(scene.FiniteState):
            raise RuntimeError("public Simulation Step did not produce a finite step")

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "canonical-garment.FCStd")
            doc.saveAs(path)
            piece_name = curved.Name
            App.closeDocument(doc.Name)
            doc = None
            reloaded = App.openDocument(path)
            scene = reloaded.getObject("ClothSimulation")
            target = reloaded.getObject("DrapeTarget")
            curved = reloaded.getObject(piece_name)
            changed_seam = reloaded.getObject("Seam")
            if scene is None or target is None or curved is None or changed_seam is None:
                raise RuntimeError("garment fixture did not survive save/reload")
            if target.SourceObject is None or target.SourceObject.Name != "AcceptanceTarget":
                raise RuntimeError("persistent DrapeTarget source was not restored")
            if curved.Sketch is None or str(curved.GeometryAuthority) != "Sketcher":
                raise RuntimeError("native Sketcher authority was not restored")
            if str(changed_seam.Status) != "Valid":
                raise RuntimeError("reloaded curved seam lost validity: %s" % changed_seam.Status)

            dimensional = curved.Sketch.addConstraint(Sketcher.Constraint("Radius", 2, 50.0))
            curved.Sketch.renameConstraint(dimensional, "UpstreamSeamCurveRadius")
            curved.Sketch.setDatum(dimensional, App.Units.Quantity("60 mm"))
            reloaded.recompute()
            if abs(float(curved.Height) - 60.0) > 1e-6:
                raise RuntimeError("native Sketcher edit did not update PatternPiece geometry")
            if str(changed_seam.Status) not in {"Changed reference", "Missing reference"}:
                raise RuntimeError("native Sketcher parameter edit did not invalidate downstream seam: %s" % changed_seam.Status)

            target_body = reloaded.getObject("AcceptanceTarget")
            target_body.Placement.Base.x += 15.0
            reloaded.recompute()
            from freecad_cloth.simulation.DrapeTarget import target_status
            if target_status(target)["state"] != "stale":
                raise RuntimeError("upstream CAD target edit did not invalidate collision target")
            Gui.runCommand("ClothDrape_RefreshTarget", 0)
            reloaded.recompute()
            Gui.Selection.clearSelection(); Gui.Selection.addSelection(scene)
            Gui.runCommand("ClothSimulation_Reset", 0)
            Gui.runCommand("ClothSimulation_Step", 0)
            reloaded.recompute()
            if int(scene.Steps) < 1 or not bool(scene.FiniteState):
                raise RuntimeError("simulation did not rerun after save/reload and upstream invalidation")
            App.closeDocument(reloaded.Name)
        print("canonical garment end-to-end acceptance passed", flush=True)
    finally:
        _close_task()
        if doc is not None:
            name = None
            try:
                name = doc.Name
            except ReferenceError:
                pass
            if name and name in App.listDocuments():
                App.closeDocument(name)


if __name__ == "__main__":
    run_acceptance()
