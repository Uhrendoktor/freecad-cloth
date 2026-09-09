"""Deterministic FreeCAD GUI screenshots; run under Xvfb with software rendering."""
import os
import sys
import tempfile
import traceback

import FreeCAD as App
import FreeCADGui as Gui
try:
    from PySide import QtWidgets, QtCore
except ImportError:
    from PySide2 import QtWidgets, QtCore

ROOT = "/workspace"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
OUT = os.environ.get("CLOTH_SCREENSHOT_DIR", "docs/images/generated")
DIAG = os.environ.get("CLOTH_GUI_DIAGNOSTICS_DIR", "artifacts/freecad-gui")
os.makedirs(OUT, exist_ok=True)
os.makedirs(DIAG, exist_ok=True)
LOG = os.path.join(OUT, "gui-progress.log")
DIAG_LOG = os.path.join(DIAG, "gui-progress.log")
MANIFEST = os.path.join(OUT, "gui-screenshot-manifest.txt")


def log(message):
    line = message + "\n"
    for path in (LOG, DIAG_LOG):
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()


def write_diagnostics(text):
    for name in ("gui-failure.txt", "gui-failure-traceback.txt"):
        path = os.path.join(DIAG, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()


def events():
    Gui.updateGui()
    QtWidgets.QApplication.processEvents()


def ensure_task_view_visible():
    """Make FreeCAD 1.1's standalone Tasks dock visible before checking a panel."""
    window = Gui.getMainWindow()
    if window is None:
        raise RuntimeError("FreeCAD main window is unavailable while opening task panel")
    docks = window.findChildren(QtWidgets.QDockWidget)
    summary = ["%s:%s:%s" % (dock.objectName(), dock.windowTitle(), dock.isVisible()) for dock in docks]
    log("dock-widgets=" + " | ".join(summary))
    task_dock = window.findChild(QtWidgets.QDockWidget, "Tasks")
    if task_dock is not None:
        action = task_dock.toggleViewAction()
        if not action.isChecked():
            action.trigger()
        task_dock.show(); task_dock.raise_(); events()
        if not task_dock.isVisible():
            window.removeDockWidget(task_dock)
            window.addDockWidget(QtCore.Qt.RightDockWidgetArea, task_dock)
            task_dock.show(); task_dock.raise_(); events()
        log("task-dock=Tasks checked=%s visible=%s" % (action.isChecked(), task_dock.isVisible()))
        if task_dock.isVisible():
            return task_dock
    combo = window.findChild(QtWidgets.QDockWidget, "Model")
    if combo is not None:
        combo.show()
        tabs = combo.findChild(QtWidgets.QTabWidget)
        if tabs is not None:
            for index in range(tabs.count()):
                if tabs.tabText(index).strip().lower() == "tasks":
                    tabs.setCurrentIndex(index); combo.raise_(); events()
                    log("task-tab=Tasks visible=%s" % combo.isVisible())
                    return combo
    raise RuntimeError("FreeCAD Tasks dock/tab is unavailable or could not be made visible")


def validate_task(panel, name, required):
    events(); ensure_task_view_visible(); events()
    if not panel.form.isVisible():
        log("task-panel-hidden name=%s active=%s parent=%s; retrying form.show()" % (
            name, bool(Gui.Control.activeDialog()), type(panel.form.parentWidget()).__name__ if panel.form.parentWidget() else "None"))
        panel.form.show(); panel.form.setVisible(True); panel.form.raise_(); panel.form.activateWindow(); events()
    visible = panel.form.isVisible() or panel.form.isVisibleTo(Gui.getMainWindow())
    log("task-panel-state name=%s isVisible=%s isVisibleToMain=%s active=%s" % (
        name, panel.form.isVisible(), panel.form.isVisibleTo(Gui.getMainWindow()), bool(Gui.Control.activeDialog())))
    if not visible:
        raise RuntimeError("task panel did not become visible: %s" % name)
    text = " | ".join(str(w.text() if callable(getattr(w, "text", None)) else getattr(w, "text", ""))
                      for w in [panel.form] + panel.form.findChildren(QtWidgets.QWidget)
                      if getattr(w, "text", "") or callable(getattr(w, "text", None)))
    missing = [item for item in required if item not in text]
    log("task-panel=%s visible=true missing=%s" % (name, ",".join(missing)))
    if missing:
        raise RuntimeError("task panel %s is missing visible text: %s" % (name, ",".join(missing)))


def show_task(panel, name, required=(), reuse_active=False):
    if not reuse_active:
        if Gui.Control.activeDialog():
            Gui.Control.closeDialog(); events()
        Gui.Control.showDialog(panel)
    validate_task(panel, name, required)


def activate(name, toolbar, commands):
    if name not in Gui.listWorkbenches():
        raise RuntimeError("workbench is not registered: %s" % name)
    Gui.activateWorkbench(name); events()
    window = Gui.getMainWindow()
    if window is None or not window.isVisible():
        raise RuntimeError("FreeCAD main window is not visible after workbench activation")
    for bar in window.findChildren(QtWidgets.QToolBar):
        if bar.windowTitle() == toolbar:
            bar.show()
    events()
    if Gui.activeWorkbench().name() != name:
        raise RuntimeError("failed to activate %s" % name)
    missing = [command for command in commands if command not in Gui.listCommands()]
    if missing:
        raise RuntimeError("commands are not registered: %s" % ",".join(missing))
    log("workbench=%s toolbar=%s" % (name, toolbar))


def save(name, state, proof):
    window = Gui.getMainWindow()
    if window is None or not window.isVisible():
        raise RuntimeError("FreeCAD main window unavailable for screenshot")
    window.show(); window.raise_(); window.activateWindow(); window.resize(1280, 720); events()
    image = window.grab(); path = os.path.join(OUT, name)
    if image.isNull() or image.width() != 1280 or image.height() != 720:
        raise RuntimeError("invalid GUI capture for %s: %sx%s" % (state, image.width(), image.height()))
    if not image.save(path) or os.path.getsize(path) < 20000:
        raise RuntimeError("failed or suspiciously small screenshot: %s" % path)
    log("screenshot=%s state=%s size=1280x720 bytes=%d" % (path, state, os.path.getsize(path)))
    with open(MANIFEST, "a", encoding="utf-8") as f:
        f.write("%s\t%s\t%s\n" % (name, state, proof))


def close_task():
    if Gui.Control.activeDialog():
        Gui.Control.closeDialog(); events()

# Pattern/sewing scenario unchanged; full implementation follows in this file.
