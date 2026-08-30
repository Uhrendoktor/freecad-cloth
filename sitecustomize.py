import sys


# FreeCAD 1.1.x keeps the Task View as a separate dock. In the Xvfb CI
# session it can start hidden, so make it available before the screenshot
# harness opens its first task dialog. Scope this compatibility hook strictly
# to the GUI screenshot script; normal Python/test processes are unaffected.
if any("tests/freecad_screenshot.py" in str(arg) for arg in sys.argv):
    try:
        import FreeCADGui as _Gui
        from PySide import QtCore as _QtCore

        def _show_task_view():
            try:
                if _Gui.getMainWindow() is not None:
                    _Gui.Control.showTaskView()
                    return
            except Exception:
                pass
            _QtCore.QTimer.singleShot(250, _show_task_view)

        _QtCore.QTimer.singleShot(250, _show_task_view)
    except Exception:
        pass
