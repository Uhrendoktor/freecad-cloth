"""Bootstrap a FreeCAD GUI acceptance script from a neutral startup directory."""
import os
import runpy
import sys

import FreeCADGui as Gui


ROOT = "/workspace"
script = os.environ["CLOTH_CI_SCRIPT"]

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

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

runpy.run_path(script, run_name="__main__")
