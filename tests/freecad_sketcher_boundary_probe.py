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

app = QtWidgets.QApplication.instance()
if app is not None:
    app.quit()
mark("quit-requested")
