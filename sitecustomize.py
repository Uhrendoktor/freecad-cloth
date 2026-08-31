"""FreeCAD CI compatibility shims loaded before test scripts."""

import sys

# Qt 6 removed QPixmap.pixel(); FreeCAD CI uses the QImage implementation.
try:
    from PySide6 import QtGui, QtWidgets, QtCore
except Exception:
    QtGui = None
    QtWidgets = None
    QtCore = None

if QtGui is not None:
    QPixmap = QtGui.QPixmap
    if not hasattr(QPixmap, "pixel"):
        def _pixel(self, x, y):
            return self.toImage().pixel(x, y)
        try:
            QPixmap.pixel = _pixel
        except (AttributeError, TypeError):
            pass


# FreeCAD 1.1 uses a separate Tasks dock. In a config-less Xvfb session the
# Model dock is visible but Tasks is hidden. Gui.Control.showDialog() populates
# the task view but does not necessarily make the dock visible. Keep a short
# timer alive for the screenshot scenario so the dock is raised both before
# and immediately after each task dialog is created.
try:
    import FreeCADGui as Gui
    if QtWidgets is not None and QtCore is not None and any("freecad_screenshot.py" in str(arg) for arg in sys.argv):
        def _show_tasks():
            window = Gui.getMainWindow()
            if window is None:
                return
            tasks = window.findChild(QtWidgets.QDockWidget, "Tasks")
            if tasks is not None:
                tasks.show()
                tasks.raise_()
                Gui.updateGui()

        _task_timer = QtCore.QTimer()
        _task_timer.setInterval(25)
        _task_ticks = [0]

        def _ensure_tasks():
            _task_ticks[0] += 1
            _show_tasks()
            if _task_ticks[0] >= 200:
                _task_timer.stop()
                _task_timer.deleteLater()

        _task_timer.timeout.connect(_ensure_tasks)
        _task_timer.start()
except Exception:
    pass


def _finish_freecad_screenshot(frame, event, arg):
    """Hard-exit only when the screenshot script's module frame returns."""
    if event == "return":
        filename = frame.f_code.co_filename.replace("\\", "/")
        if (filename.endswith("/tests/freecad_screenshot.py")
                and frame.f_code.co_name == "<module>"):
            import os
            os._exit(0)
    return _finish_freecad_screenshot


# FreeCAD executes the screenshot file inside its GUI process. Returning from
# the file does not terminate that process, so terminate exactly when the
# module frame returns. This avoids touching Gui.Control or Qt extension
# objects and cannot fire merely because an individual helper function returns.
sys.settrace(_finish_freecad_screenshot)
