"""FreeCAD CI compatibility shims loaded before test scripts."""

# Qt 6 removed QPixmap.pixel(); pixel data is exposed through QImage instead.
# The GUI regression test still uses the Qt 5-era call, so keep that call
# compatible in the FreeCAD CI interpreter without changing application code.
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
    if event == "return":
        filename = frame.f_code.co_filename.replace("\\", "/")
        if filename.endswith("/tests/freecad_screenshot.py"):
            try:
                from PySide6 import QtWidgets
                app = QtWidgets.QApplication.instance()
                if app is not None:
                    app.quit()
            except Exception:
                pass
    return _finish_freecad_screenshot


# The FreeCAD GUI executable owns the Qt event loop. The screenshot script is
# executed as a script by FreeCAD and therefore returning from the script does
# not automatically terminate the GUI process. Trace its final frame return
# and quit Qt so the CI command can terminate cleanly instead of timing out.
import sys
sys.settrace(_finish_freecad_screenshot)
