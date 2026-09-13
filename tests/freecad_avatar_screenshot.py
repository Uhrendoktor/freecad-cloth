"""Deterministic six-direction visual audit of the production avatar mesh."""
import os
import traceback

import FreeCAD as App
import FreeCADGui as Gui
try:
    from PySide import QtWidgets
except ImportError:
    from PySide2 import QtWidgets

ROOT = "/workspace"
if ROOT not in __import__("sys").path:
    __import__("sys").path.insert(0, ROOT)
OUT = os.environ.get("CLOTH_SCREENSHOT_DIR", "docs/images/generated")
os.makedirs(OUT, exist_ok=True)
LOG = os.path.join(OUT, "avatar-gui-progress.log")


def log(message):
    with open(LOG, "a", encoding="utf-8") as handle:
        handle.write(message + "\n")


def events():
    Gui.updateGui()
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.processEvents()


def hide_task_docks(window):
    """Keep GUI chrome available for the audit but do not rely on it for captures."""
    hidden = []
    for dock in window.findChildren(QtWidgets.QDockWidget):
        title = str(dock.windowTitle()).strip().lower()
        if "task" in title:
            dock.hide()
            hidden.append(str(dock.windowTitle()))
    if hidden:
        log("hidden-task-docks=%s" % ",".join(hidden))
    events()


def zoom_for_direction(view, direction):
    """Fit the orthographic camera and compensate for the small top/bottom projection."""
    view.fitAll()
    steps = 3 if direction in ("top", "bottom") else 1
    for _ in range(steps):
        view.zoomIn()
    log("camera-zoom direction=%s steps=%d" % (direction, steps))
    events()


def save(view, name, state):
    """Render only the 3D view so README images are unobstructed model evidence."""
    path = os.path.join(OUT, name)
    view.saveImage(path, 1280, 720, "White")
    if not os.path.isfile(path) or os.path.getsize(path) < 5000:
        raise RuntimeError("failed or suspiciously small screenshot: %s" % path)
    with open(path, "rb") as handle:
        header = handle.read(24)
    if header[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError("invalid PNG capture for %s" % state)
    width = int.from_bytes(header[16:20], "big")
    height = int.from_bytes(header[20:24], "big")
    if (width, height) != (1280, 720):
        raise RuntimeError("invalid rendered dimensions for %s: %sx%s" % (state, width, height))
    log("screenshot=%s state=%s bytes=%d" % (path, state, os.path.getsize(path)))


def main():
    log("avatar-script-start")
    window = Gui.getMainWindow()
    if window is None or not window.isVisible():
        raise RuntimeError("FreeCAD GUI did not launch")
    window.show(); events()

    init_gui = os.path.join(ROOT, "InitGui.py")
    exec(compile(open(init_gui, encoding="utf-8").read(), init_gui, "exec"), globals(), globals())
    events()
    hide_task_docks(window)

    from freecad_cloth.avatar.AvatarCommands import create_avatar

    doc = App.newDocument("ClothAvatarVisualAudit")
    try:
        avatar = create_avatar(attach_collision=False, doc=doc)
        if str(getattr(avatar, "AvatarStatus", "")) != "Valid":
            raise RuntimeError("avatar provider did not produce a valid mesh")
        if int(getattr(avatar, "MeshVertexCount", 0)) <= 100 or int(getattr(avatar, "MeshTriangleCount", 0)) <= 100:
            raise RuntimeError("avatar visual fixture does not contain a real humanoid mesh")
        avatar.ViewObject.DisplayMode = "Flat Lines"
        avatar.ViewObject.ShapeColor = (0.72, 0.72, 0.72)
        avatar.ViewObject.LineColor = (0.20, 0.20, 0.20)
        avatar.ViewObject.LineWidth = 1.0
        doc.recompute()

        view = Gui.activeDocument().activeView()
        view.setAnimationEnabled(False)
        view.setCameraType("Orthographic")
        directions = (
            ("front", "viewFront"),
            ("rear", "viewRear"),
            ("left", "viewLeft"),
            ("right", "viewRight"),
            ("top", "viewTop"),
            ("bottom", "viewBottom"),
        )
        for direction, method_name in directions:
            getattr(view, method_name)()
            zoom_for_direction(view, direction)
            save(view, "cloth-avatar-%s.png" % direction, "Avatar audit %s" % direction)
        log("avatar-script-pass")
    finally:
        if doc.Name in App.listDocuments():
            App.closeDocument(doc.Name)
        events()
        window.close()
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.quit()


try:
    main()
except BaseException as error:
    print("AVATAR SCREENSHOT FAILURE: %r" % (error,), flush=True)
    print(traceback.format_exc(), flush=True)
    log("avatar-script-fail exception=%r" % (error,))
    raise
