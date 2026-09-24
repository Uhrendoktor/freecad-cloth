"""Bootstrap a FreeCAD GUI acceptance script from a neutral startup directory."""
import os
import runpy
import sys

ROOT = "/workspace"
script = os.environ["CLOTH_CI_SCRIPT"]

# FreeCAD delayed startup must not see the repository on sys.path.
sys.path[:] = [p for p in sys.path if p != ROOT]

import FreeCADGui as Gui  # noqa: E402

window = Gui.getMainWindow()
if window is None:
    raise RuntimeError("FreeCAD GUI main window is not available")

window.show()
Gui.updateGui()

try:
    from PySide import QtWidgets
except ImportError:
    from PySide2 import QtWidgets

app = QtWidgets.QApplication.instance()
if app is not None:
    app.processEvents()

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

runpy.run_path(script, run_name="__main__")
