"""Deterministic GUI visual-regression scenarios; run under Xvfb with FreeCAD."""
import os
import sys
import traceback

import FreeCAD as App
import FreeCADGui as Gui
try:
    from PySide import QtWidgets
except ImportError:
    from PySide2 import QtWidgets

REPO_ROOT = "/workspace"
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
OUT = os.environ.get("CLOTH_SCREENSHOT_DIR", "docs/images/generated")
os.makedirs(OUT, exist_ok=True)
DEBUG = os.path.join(OUT, "gui-progress.log")
MANIFEST = os.path.join(OUT, "gui-screenshot-manifest.txt")

def progress(message):
    with open(DEBUG, "a", encoding="utf-8") as handle:
        handle.write(message + "\n")
        handle.flush()

def toolbars():
    window = Gui.getMainWindow()
    return [] if window is None else [bar.windowTitle() for bar in window.findChildren(QtWidgets.QToolBar) if bar.isVisible()]

def docks():
    window = Gui.getMainWindow()
    return [] if window is None else [dock.windowTitle() for dock in window.findChildren(QtWidgets.QDockWidget) if dock.isVisible()]

def activate_workbench(internal_name, toolbar_name, expected_commands):
    available = Gui.listWorkbenches()
    progress("workbenches=" + ",".join(sorted(available.keys())))
    if internal_name not in available:
        raise RuntimeError("workbench is not registered: %s" % internal_name)
    Gui.activateWorkbench(internal_name)
    Gui.updateGui()
    window = Gui.getMainWindow()
    if window is None:
        raise RuntimeError("FreeCAD main window is unavailable")
    for bar in window.findChildren(QtWidgets.QToolBar):
        if bar.windowTitle() == toolbar_name:
            bar.show()
    Gui.updateGui()
    active = Gui.activeWorkbench().name()
    visible = toolbars()
    missing = [name for name in expected_commands if name not in Gui.listCommands()]
    progress("workbench=%s active=%s toolbar=%s visible_toolbars=%s missing_commands=%s docks=%s" % (internal_name, active, toolbar_name, ",".join(visible), ",".join(missing), ",".join(docks())))
    if active != internal_name:
        raise RuntimeError("failed to activate %s (active=%s)" % (internal_name, active))
    if toolbar_name not in visible:
        raise RuntimeError("toolbar is not visible: %s" % toolbar_name)
    if missing:
        raise RuntimeError("commands are not registered: %s" % ",".join(missing))

def _panel_visible(panel):
    form = getattr(panel, "form", None)
    if form is None:
        return False
    if form.isVisible():
        return True
    window = Gui.getMainWindow()
    if window is None:
        return False
    # FreeCAD may reparent the form into the Tasks dock and leave the Python
    # wrapper's top-level visibility flag false. Check the actual widget tree.
    for widget in window.findChildren(QtWidgets.QWidget):
        if widget is form or form in widget.findChildren(QtWidgets.QWidget):
            if widget.isVisible() and widget.isWindow() is False:
                return True
    return False

def show_task(panel, state_name):
    Gui.Control.showDialog(panel)
    Gui.updateGui()
    for _ in range(20):
        QtWidgets.QApplication.processEvents()
        if _panel_visible(panel):
            break
    visible = _panel_visible(panel)
    progress("task-panel=%s visible=%s docks=%s" % (state_name, visible, ",".join(docks())))
    if not visible:
        raise RuntimeError("task panel did not become visible: %s" % state_name)

def panel_text(panel):
    if panel is None or getattr(panel, "form", None) is None:
        return ""
    texts = []
    for widget in [panel.form] + panel.form.findChildren(QtWidgets.QWidget):
        for attr in ("text", "title"):
            value = getattr(widget, attr, None)
            if callable(value):
                try: value = value()
                except Exception: continue
            if value: texts.append(str(value))
        value = getattr(widget, "currentText", None)
        if callable(value):
            try: value = value()
            except Exception: value = None
        if value: texts.append(str(value))
    return " | ".join(texts)

def require_panel(panel, state_name, required):
    if not _panel_visible(panel):
        raise RuntimeError("task panel is not visible: %s" % state_name)
    text = panel_text(panel)
    missing = [item for item in required if item not in text]
    progress("panel-content=%s missing=%s" % (state_name, ",".join(missing)))
    if missing:
        raise RuntimeError("task panel %s is missing visible text: %s" % (state_name, ",".join(missing)))

def set_top_camera():
    view = Gui.activeDocument().activeView(); view.viewTop(); view.fitAll(); Gui.updateGui(); QtWidgets.QApplication.processEvents()

def set_axon_camera():
    view = Gui.activeDocument().activeView(); view.viewAxonometric(); view.fitAll(); Gui.updateGui(); QtWidgets.QApplication.processEvents()

def add_line_feature(doc, name, segments, width=4.0):
    import Part
    feature = doc.addObject("Part::Feature", name); feature.Label = name
    feature.Shape = Part.makeCompound([Part.makeLine(a, b) for a, b in segments]); feature.ViewObject.LineWidth = width
    feature.ViewObject.LineColor = (0.85, 0.15, 0.15); return feature

def add_pattern_markers(doc, front, back):
    import FreeCAD as FC
    front_x = float(front.Placement.Base.x); back_x = float(back.Placement.Base.x); markers = []
    for name, x in (("Front notch marker", front_x + 70.0), ("Back notch marker", back_x + 70.0)):
        markers.append(add_line_feature(doc, name, [(FC.Vector(x - 5, 90, .8), FC.Vector(x, 84, .8)), (FC.Vector(x, 84, .8), FC.Vector(x + 5, 90, .8))]))
    markers.append(add_line_feature(doc, "Front grainline marker", [(FC.Vector(front_x + 70, 12, .8), FC.Vector(front_x + 70, 78, .8)), (FC.Vector(front_x + 70, 78, .8), FC.Vector(front_x + 66, 70, .8)), (FC.Vector(front_x + 70, 78, .8), FC.Vector(front_x + 74, 70, .8))]))
    progress("pattern-markers=notches+grainline count=%s" % len(markers)); return markers

def add_sewing_arrows(doc, front, back):
    import FreeCAD as FC
    arrows = []
    for name, x0, x1 in (("Sew direction A", front.Placement.Base.x + 140, front.Placement.Base.x + 128), ("Sew direction B", back.Placement.Base.x, back.Placement.Base.x + 12)):
        head = FC.Vector(x0, 45, .9); tail = FC.Vector(x1, 45, .9); left = FC.Vector(x0 - (3 if x0 < x1 else -3), 49, .9); right = FC.Vector(x0 - (3 if x0 < x1 else -3), 41, .9)
        arrows.append(add_line_feature(doc, name, [(tail, head), (head, left), (head, right)]))
    return arrows

def image_is_useful(path, state_name):
    if not os.path.isfile(path): raise RuntimeError("screenshot does not exist: %s" % path)
    if os.path.getsize(path) < 20000: raise RuntimeError("screenshot is suspiciously small: %s" % path)
    image = Gui.getMainWindow().grab()
    if image.isNull() or image.width() < 1000 or image.height() < 600: raise RuntimeError("captured window is blank/partial for %s" % state_name)
    samples = {int(image.pixel(x, y)) for y in range(0, image.height(), max(1, image.height() // 24)) for x in range(0, image.width(), max(1, image.width() // 32))}
    if len(samples) < 80: raise RuntimeError("screenshot is visually uniform for %s" % state_name)

def save_window(filename, state_name, proof):
    Gui.updateGui(); QtWidgets.QApplication.processEvents(); window = Gui.getMainWindow()
    if window is None: raise RuntimeError("FreeCAD main window is unavailable")
    window.show(); window.raise_(); window.activateWindow(); window.resize(1280, 720); QtWidgets.QApplication.processEvents()
    path = os.path.join(OUT, filename); image = window.grab()
    if image.isNull() or not image.save(path): raise RuntimeError("failed to save screenshot: %s" % path)
    image_is_useful(path, state_name)
    with open(MANIFEST, "a", encoding="utf-8") as handle: handle.write("%s\t%s\t%s\n" % (filename, state_name, proof))

# Keep the scenario body from main intact; this explicit entry point guarantees cleanup.
def run_scenario():
    raise RuntimeError("scenario body must be restored from main before running")

try:
    init_gui = os.path.join(REPO_ROOT, "InitGui.py")
    exec(compile(open(init_gui, encoding="utf-8").read(), init_gui, "exec"), globals(), globals())
    progress("gui-modules-import-ok")
    run_scenario()
except Exception:
    progress("scenario-error")
    progress(traceback.format_exc())
    raise
finally:
    try:
        Gui.Control.closeDialog()
    except Exception:
        pass
    try:
        if App.ActiveDocument:
            App.closeDocument(App.ActiveDocument.Name)
    except Exception:
        pass
    try:
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.quit()
            app.processEvents()
    except Exception:
        pass
    # Direct execution by FreeCAD's Python runner does not necessarily leave
    # the Qt event loop when the module returns. Exit explicitly after cleanup.
    if __name__ == "__main__":
        os._exit(0)
