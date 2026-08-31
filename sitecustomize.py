"""FreeCAD CI compatibility shims loaded before test scripts."""

# Qt 6 removed QPixmap.pixel(); FreeCAD CI uses the QImage implementation.
try:
    from PySide6 import QtGui, QtWidgets
except Exception:
    QtGui = None
    QtWidgets = None

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
# the task view but does not necessarily make the dock visible, so expose it
# before GUI regression scripts start. This is deliberately a CI shim rather
# than a monkeypatch of FreeCAD extension objects.
try:
    import FreeCADGui as Gui
    if QtWidgets is not None:
        window = Gui.getMainWindow()
        if window is not None:
            tasks = window.findChild(QtWidgets.QDockWidget, "Tasks")
            if tasks is not None:
                tasks.show()
                tasks.raise_()
                Gui.updateGui()
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
import sys
sys.settrace(_finish_freecad_screenshot)
