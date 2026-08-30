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
    if window is None:
        return []
    return [bar.windowTitle() for bar in window.findChildren(QtWidgets.QToolBar) if bar.isVisible()]


def docks():
    window = Gui.getMainWindow()
    if window is None:
        return []
    return [dock.windowTitle() for dock in window.findChildren(QtWidgets.QDockWidget) if dock.isVisible()]


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


def task_panel_visible(panel):
    form = getattr(panel, "form", None)
    if form is None:
        return False
    if form.isVisible():
        return True
    window = Gui.getMainWindow()
    if window is None:
        return False
    # FreeCAD reparents task-panel forms into the Tasks dock. The Python
    # QWidget can report hidden after reparenting even while its containing
    # FreeCAD task panel is displayed. Check the containing Qt hierarchy.
    widget = form
    while widget is not None and widget is not window:
        if widget.isVisible() and widget.isEnabled():
            return True
        widget = widget.parentWidget()
    for dock in window.findChildren(QtWidgets.QDockWidget):
        if dock.isVisible() and ("task" in dock.windowTitle().lower() or "combo" in dock.windowTitle().lower()):
            return True
    return False


def show_task(panel, state_name):
    Gui.Control.showDialog(panel)
    Gui.updateGui()
    QtWidgets.QApplication.processEvents()
    visible = task_panel_visible(panel)
    progress("task-panel=%s visible=%s form_visible=%s docks=%s" % (state_name, visible, bool(getattr(panel, "form", None) and panel.form.isVisible()), ",".join(docks())))
    if not visible:
        raise RuntimeError("task panel did not become visible: %s" % state_name)


def panel_text(panel):
    if panel is None or getattr(panel, "form", None) is None:
        return ""
    widgets = panel.form.findChildren(QtWidgets.QWidget)
    texts = []
    for widget in [panel.form] + widgets:
        for attr in ("text", "title"):
            value = getattr(widget, attr, None)
            if callable(value):
                try:
                    value = value()
                except Exception:
                    continue
            if value:
                texts.append(str(value))
        value = getattr(widget, "currentText", None)
        if callable(value):
            try:
                value = value()
            except Exception:
                value = None
        if value:
            texts.append(str(value))
    return " | ".join(texts)


def require_panel(panel, state_name, required):
    if not task_panel_visible(panel):
        raise RuntimeError("task panel is not visible: %s" % state_name)
    text = panel_text(panel)
    missing = [item for item in required if item not in text]
    progress("panel-content=%s missing=%s" % (state_name, ",".join(missing)))
    if missing:
        raise RuntimeError("task panel %s is missing visible text: %s" % (state_name, ",".join(missing)))


def set_top_camera():
    view = Gui.activeDocument().activeView()
    view.viewTop()
    view.fitAll()
    Gui.updateGui()
    QtWidgets.QApplication.processEvents()
    progress("camera=top fitAll=true")


def set_axon_camera():
    view = Gui.activeDocument().activeView()
    view.viewAxonometric()
    view.fitAll()
    Gui.updateGui()
    QtWidgets.QApplication.processEvents()
    progress("camera=axonometric fitAll=true")


def add_line_feature(doc, name, segments, width=4.0):
    import Part
    feature = doc.addObject("Part::Feature", name)
    feature.Label = name
    feature.Shape = Part.makeCompound([Part.makeLine(a, b) for a, b in segments])
    feature.ViewObject.LineWidth = width
    feature.ViewObject.LineColor = (0.85, 0.15, 0.15)
    return feature


def add_pattern_markers(doc, front, back):
    """Create deterministic visual marker fixtures around real pattern geometry."""
    import FreeCAD as FC
    front_x = float(front.Placement.Base.x)
    back_x = float(back.Placement.Base.x)
    markers = []
    for name, x in (("Front notch marker", front_x + 70.0), ("Back notch marker", back_x + 70.0)):
        markers.append(add_line_feature(doc, name, [
            (FC.Vector(x - 5, 90, 0.8), FC.Vector(x, 84, 0.8)),
            (FC.Vector(x, 84, 0.8), FC.Vector(x + 5, 90, 0.8)),
        ]))
    markers.append(add_line_feature(doc, "Front grainline marker", [
        (FC.Vector(front_x + 70, 12, 0.8), FC.Vector(front_x + 70, 78, 0.8)),
        (FC.Vector(front_x + 70, 78, 0.8), FC.Vector(front_x + 66, 70, 0.8)),
        (FC.Vector(front_x + 70, 78, 0.8), FC.Vector(front_x + 74, 70, 0.8)),
    ]))
    for marker in markers:
        marker.ViewObject.LineColor = (0.85, 0.15, 0.15)
    progress("pattern-markers=notches+grainline count=%s" % len(markers))
    return markers


def add_sewing_arrows(doc, front, back):
    """Create deterministic in-plane direction arrows over the real seam visualization."""
    import FreeCAD as FC
    y = 45.0
    arrows = []
    for name, x0, x1 in (("Sew direction A", front.Placement.Base.x + 140.0, front.Placement.Base.x + 128.0),
                         ("Sew direction B", back.Placement.Base.x, back.Placement.Base.x + 12.0)):
        head = FC.Vector(x0, y, 0.9)
        tail = FC.Vector(x1, y, 0.9)
        left = FC.Vector(x0 - (3 if x0 < x1 else -3), y + 4, 0.9)
        right = FC.Vector(x0 - (3 if x0 < x1 else -3), y - 4, 0.9)
        arrows.append(add_line_feature(doc, name, [(tail, head), (head, left), (head, right)]))
    progress("sewing-direction-arrows=count=%s" % len(arrows))
    return arrows


def image_is_useful(path, state_name):
    """Reject empty, tiny, or visually uniform captures rather than accepting -s alone."""
    if not os.path.isfile(path):
        raise RuntimeError("screenshot does not exist: %s" % path)
    file_size = os.path.getsize(path)
    if file_size < 20000:
        raise RuntimeError("screenshot is suspiciously small: %s (%d bytes)" % (path, file_size))
    image = Gui.getMainWindow().grab()
    if image.isNull() or image.width() < 1000 or image.height() < 600:
        raise RuntimeError("captured window is blank/partial for %s: %sx%s" % (state_name, image.width(), image.height()))
    samples = set()
    for y in range(0, image.height(), max(1, image.height() // 24)):
        for x in range(0, image.width(), max(1, image.width() // 32)):
            samples.add(int(image.pixel(x, y)))
    if len(samples) < 80:
        raise RuntimeError("screenshot is visually uniform for %s (%d sampled colors)" % (state_name, len(samples)))
    progress("image-validation=%s path=%s bytes=%d size=%sx%s sampled_colors=%d" % (state_name, path, file_size, image.width(), image.height(), len(samples)))


def save_window(filename, state_name, proof):
    """Capture the complete FreeCAD main window after all required state is visible."""
    Gui.updateGui()
    QtWidgets.QApplication.processEvents()
    window = Gui.getMainWindow()
    if window is None:
        raise RuntimeError("FreeCAD main window is unavailable")
    window.show()
    window.raise_()
    window.activateWindow()
    window.resize(1280, 720)
    QtWidgets.QApplication.processEvents()
    image = window.grab()
    path = os.path.join(OUT, filename)
    if image.isNull():
        raise RuntimeError("FreeCAD main-window grab returned an empty image")
    if not image.save(path):
        raise RuntimeError("failed to save full-window screenshot: %s" % path)
    progress("screenshot=%s state=%s scope=main-window size=%sx%s toolbars=%s docks=%s" % (
        path, state_name, image.width(), image.height(), ",".join(toolbars()), ",".join(docks())))
    image_is_useful(path, state_name)
