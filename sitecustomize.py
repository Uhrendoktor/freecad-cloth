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

# FreeCAD's Task View can be preference-gated in a fresh AppImage/container.
# The preference alone is not sufficient when the Combo View has already been
# constructed hidden: showTaskView() must be invoked after the GUI event loop
# exists. Restrict this bootstrap to the visual-regression process.
import os
import sys

if os.path.basename(sys.argv[0]) == "freecad_screenshot.py":
    try:
        import FreeCAD as App
        import FreeCADGui as Gui
        group = App.ParamGet("User parameter:BaseApp/Preferences/DockWindows/TaskView")
        group.SetBool("Enabled", True)
        group.SetBool("RestoreWidth", True)

        # Queue the GUI operation rather than calling it during Python startup;
        # at that point the main window/Combo View may not exist yet.
        try:
            from PySide import QtCore
        except Exception:
            from PySide2 import QtCore

        def _show_task_view():
            try:
                Gui.Control.showTaskView()
                Gui.updateGui()
            except Exception:
                pass

        QtCore.QTimer.singleShot(0, _show_task_view)

        out = "/workspace/docs/images/generated"
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "task-view-bootstrap.log"), "w", encoding="utf-8") as handle:
            handle.write("task-view-enabled=true\n")
            handle.write("task-view-show-queued=true\n")
            handle.write("argv0=%s\n" % sys.argv[0])
    except Exception as exc:
        try:
            out = "/workspace/docs/images/generated"
            os.makedirs(out, exist_ok=True)
            with open(os.path.join(out, "task-view-bootstrap.log"), "w", encoding="utf-8") as handle:
                handle.write("task-view-bootstrap-error=%r\n" % (exc,))
        except Exception:
            pass
