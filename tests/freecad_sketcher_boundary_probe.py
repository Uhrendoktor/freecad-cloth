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
