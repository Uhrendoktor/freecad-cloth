"""FreeCAD CI compatibility shims loaded before test scripts."""

# Qt 6 removed QPixmap.pixel(); FreeCAD CI uses the QImage implementation.
try:
    from PySide6 import QtGui
except Exception:
    QtGui = None

if QtGui is not None:
    QPixmap = QtGui.QPixmap
    if not hasattr(QPixmap, "pixel"):
        def _pixel(self, x, y):
            return self.toImage().pixel(x, y)
        try:
            QPixmap.pixel = _pixel
        except (AttributeError, TypeError):
            pass


def _finish_freecad_screenshot(frame, event, arg):
    """Hard-exit only when the screenshot script's module frame returns."""
    if event == "return":
        filename = frame.f_code.co_filename.replace("\\", "/")
        if (filename.endswith("/tests/freecad_screenshot.py")
                and frame.f_code.co_name == "<module>"):
            # The script has completed. FreeCAD's outer GUI process otherwise
            # remains in its Qt event loop after AppRun executes the script.
            import os
            os._exit(0)
    return _finish_freecad_screenshot


# FreeCAD executes the screenshot file inside its GUI process. Returning from
# the file does not terminate that process, so terminate exactly when the
# module frame returns. This avoids touching Gui.Control or Qt extension
# objects and cannot fire merely because an individual helper function returns.
import sys
sys.settrace(_finish_freecad_screenshot)
