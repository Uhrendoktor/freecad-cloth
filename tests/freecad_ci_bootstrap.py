"""Bootstrap a FreeCAD GUI acceptance script after delayed startup returns."""
import os
import runpy
import sys
import traceback

ROOT = "/workspace"
script = os.environ["CLOTH_CI_SCRIPT"]

# Keep the repository out of FreeCAD's own startup import path.
sys.path[:] = [p for p in sys.path if p != ROOT]

import FreeCADGui as Gui  # noqa: E402
try:
    from PySide import QtCore, QtWidgets  # noqa: E402
except ImportError:
    from PySide2 import QtCore, QtWidgets  # noqa: E402


window = Gui.getMainWindow()
if window is None:
    raise RuntimeError("FreeCAD GUI main window is not available")
window.show()


def _run_acceptance():
    app = QtWidgets.QApplication.instance()
    try:
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        runpy.run_path(script, run_name="__main__")
    except BaseException:
        traceback.print_exc()
        if app is not None:
            app.exit(1)
        return
    if app is not None:
        app.exit(0)


# FreeCAD executes positional scripts from MainWindow::delayedStartup(). Defer
# the acceptance script until that callback returns to the Qt event loop, so
# InitGui.py cannot call Gui.addWorkbench re-entrantly from delayedStartup.
QtCore.QTimer.singleShot(0, _run_acceptance)
