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
doc.recompute()
pieces = [obj for obj in doc.Objects if getattr(obj, "PatternType", "") == "PatternPiece"]
mark("pattern-pieces-count-" + str(len(pieces)))

import Sketcher  # noqa: E402
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
