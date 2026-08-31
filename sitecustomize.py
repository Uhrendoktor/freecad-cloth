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

# FreeCAD's Task View is preference-gated. A fresh AppImage/container can have
# BaseApp/Preferences/DockWindows/TaskView/Enabled unset/false. In that state
# Gui.Control.showDialog() has no Task View dock into which a Python task panel
# can be embedded. Normal desktop installations commonly have this enabled.
# Limit the change to the GUI screenshot process so ordinary Python/FreeCAD
# tests retain their normal preferences.
import os
import sys

if os.path.basename(sys.argv[0]) == "freecad_screenshot.py":
    try:
        import FreeCAD as App
        group = App.ParamGet("User parameter:BaseApp/Preferences/DockWindows/TaskView")
        group.SetBool("Enabled", True)
        group.SetBool("RestoreWidth", True)

        out = "/workspace/docs/images/generated"
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "task-view-bootstrap.log"), "w", encoding="utf-8") as handle:
            handle.write("task-view-enabled=true\n")
            handle.write("argv0=%s\n" % sys.argv[0])
    except Exception as exc:
        # Startup hooks must never prevent FreeCAD from launching. The normal
        # screenshot harness will expose the underlying GUI state if this
        # compatibility step cannot run in a particular FreeCAD build.
        try:
            out = "/workspace/docs/images/generated"
            os.makedirs(out, exist_ok=True)
            with open(os.path.join(out, "task-view-bootstrap.log"), "w", encoding="utf-8") as handle:
                handle.write("task-view-bootstrap-error=%r\n" % (exc,))
        except Exception:
            pass
