"""Temporary boundary probe for the Native Sketcher GUI acceptance path."""
import math
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:] = [entry for entry in sys.path if entry not in ("", str(ROOT))]

def mark(stage: str) -> None:
    print("stage=" + stage, flush=True)

mark("script-loaded")
import FreeCAD as App  # noqa: E402
mark("freecad-imported")
import FreeCADGui as Gui  # noqa: E402
mark("freecadgui-imported")
import Part  # noqa: E402
mark("part-imported")

mark("process-start")
window = Gui.getMainWindow()
mark("main-window-read")
if window is None:
    raise RuntimeError("main window missing")
window.show()
mark("window-show")
Gui.updateGui()
mark("gui-updated")
try:
    from PySide import QtWidgets
except ImportError:
    from PySide2 import QtWidgets
QtWidgets.QApplication.processEvents()
mark("events-processed")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
init_gui = ROOT / "InitGui.py"
namespace = {"__file__": str(init_gui), "__name__": "__main__"}
mark("before-initgui-exec")
exec(compile(init_gui.read_text(encoding="utf-8"), str(init_gui), "exec"), namespace, namespace)
mark("after-initgui-exec")
if "ClothPatternWorkbench" not in Gui.listWorkbenches():
    raise RuntimeError("ClothPatternWorkbench not registered")
mark("workbenches-registered")

doc = App.newDocument("SketcherBoundaryProbe")
mark("document-created")

Gui.activateWorkbench("ClothPatternWorkbench")
mark("workbench-activated")
Gui.updateGui()
QtWidgets.QApplication.processEvents()
mark("workbench-events-processed")

commands = Gui.listCommands()
mark("commands-listed")
required = ["ClothPattern_CreatePieceWithSketch", "ClothPattern_EditSketch"]
missing = [name for name in required if name not in commands]
if missing:
    raise RuntimeError("missing commands: " + ",".join(missing))
mark("commands-validated")

Gui.runCommand("ClothPattern_CreatePieceWithSketch", 0)
mark("create-command-returned")
Gui.runCommand("ClothPattern_CreatePieceWithSketch", 0)
mark("second-create-command-returned")
doc.recompute()
pieces = [obj for obj in doc.Objects if getattr(obj, "PatternType", "") == "PatternPiece"]
mark("pattern-pieces-count-" + str(len(pieces)))

curved = pieces[0]
mark("curved-piece-selected")
sketch = curved.Sketch
if sketch is None:
    raise RuntimeError("PatternPiece has no Sketch")
mark("piece-sketch-read")

sketch.Constraints = []
mark("constraints-cleared")

geometry = [
    Part.LineSegment(App.Vector(0, 0, 0), App.Vector(100, 0, 0)),
    Part.LineSegment(App.Vector(100, 0, 0), App.Vector(80, 50, 0)),
    Part.ArcOfCircle(Part.Circle(App.Vector(40, 50, 0), App.Vector(0, 0, 1), 40), 0, math.pi),
    Part.LineSegment(App.Vector(0, 50, 0), App.Vector(0, 0, 0)),
]
mark("geometry-built")

sketch.Geometry = geometry
mark("geometry-assigned")

sketch.SemanticEdgeIds = [f"{curved.PieceId}:edge:{i}" for i in range(4)]
mark("semantic-edges-assigned")

sketch.GeometryAuthority = "Sketcher"
mark("geometry-authority-assigned")

import Sketcher  # noqa: E402
sketch.addConstraint([
    Sketcher.Constraint("Coincident", 0, 2, 1, 1),
    Sketcher.Constraint("Coincident", 1, 2, 2, 1),
    Sketcher.Constraint("Coincident", 2, 2, 3, 1),
    Sketcher.Constraint("Coincident", 3, 2, 0, 1),
    Sketcher.Constraint("Horizontal", 0),
])
mark("geometric-constraints-added")

width_index = sketch.addConstraint(Sketcher.Constraint("Distance", 0, 100.0))
mark("width-constraint-added")
height_index = sketch.addConstraint(Sketcher.Constraint("Distance", 3, 50.0))
mark("height-constraint-added")

doc.recompute()
mark("sketch-recompute-complete")

audit = doc.addObject("Sketcher::SketchObject", "SketchConstraintAudit")
audit.Label = "Sketcher Constraint Audit"
mark("audit-sketch-created")

lines = [
    Part.LineSegment(App.Vector(0, 0, 0), App.Vector(40, 0, 0)),
    Part.LineSegment(App.Vector(0, 30, 0), App.Vector(40, 30, 0)),
    Part.LineSegment(App.Vector(20, -15, 0), App.Vector(20, 45, 0)),
    Part.Point(App.Vector(10, 0, 0)),
    Part.Point(App.Vector(30, 0, 0)),
    Part.LineSegment(App.Vector(0, 70, 0), App.Vector(40, 70, 0)),
    Part.LineSegment(App.Vector(0, 80, 0), App.Vector(20, 80, 0)),
]
audit.addGeometry(lines, False)
mark("audit-geometry-added")

audit.toggleConstruction(2)
mark("audit-construction-toggled")

equal_index = audit.addConstraint(Sketcher.Constraint("Equal", 0, 1))
audit.addConstraint(Sketcher.Constraint("Horizontal", 0))
audit.addConstraint(Sketcher.Constraint("Horizontal", 1))
audit.addConstraint(Sketcher.Constraint("Vertical", 2))
mark("audit-basic-constraints-added")

point_on_object_index = audit.addConstraint(Sketcher.Constraint("PointOnObject", 3, 1, 0))
mark("audit-point-on-object-added")
symmetric_index = audit.addConstraint(Sketcher.Constraint("Symmetric", 3, 1, 4, 1, 2, 1))
mark("audit-symmetric-added")
audit_span = audit.addConstraint(Sketcher.Constraint("Distance", 5, 40.0))
mark("audit-span-added")
audit_scaled = audit.addConstraint(Sketcher.Constraint("Distance", 6, 20.0))
mark("audit-scaled-added")

audit.renameConstraint(audit_span, "AuditSpan")
audit.renameConstraint(audit_scaled, "AuditScaled")
mark("audit-constraint-names-set")
audit.setExpression("Constraints[%d]" % audit_scaled, "Constraints[%d] / 2" % audit_span)
mark("audit-expression-set")
doc.recompute()
mark("audit-recompute-complete")

geometry_count = len(audit.Geometry)
audit.addExternal(curved.Sketch.Name, "Edge1")
mark("audit-external-added")
if len(audit.Geometry) != geometry_count:
    raise RuntimeError("external geometry unexpectedly changed owned geometry")
if not getattr(audit, "ExternalGeometry", ()):
    raise RuntimeError("external geometry did not persist")
mark("audit-external-validated")

curved.Placement.Base.x = -130
pieces[1].Placement.Base.x = 20
mark("piece-placements-set")

Gui.Selection.clearSelection()
Gui.Selection.addSelection(curved)
mark("pattern-piece-selected-for-edit")
Gui.runCommand("ClothPattern_EditSketch", 0)
mark("edit-sketch-command-returned")
Gui.updateGui()
QtWidgets.QApplication.processEvents()
mark("edit-sketch-events-processed")
if not Gui.activeDocument().getInEdit():
    raise RuntimeError("PatternPiece edit command did not enter Sketcher")
mark("edit-sketch-entered")
Gui.activeDocument().resetEdit()
Gui.updateGui()
QtWidgets.QApplication.processEvents()
mark("edit-sketch-reset")

mark("sketcher-imported")

sketch = doc.addObject("Sketcher::SketchObject", "BoundarySketch")
doc.recompute()
if sketch is None:
    raise RuntimeError("Sketcher object creation returned None")
mark("sketch-object-created")

App.closeDocument(doc.Name)
mark("document-closed")

app = QtWidgets.QApplication.instance()
if app is not None:
    app.quit()
mark("quit-requested")
