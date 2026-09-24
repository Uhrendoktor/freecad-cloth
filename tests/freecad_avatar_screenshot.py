"""Deterministic avatar visual audit plus a full 360-degree turntable render."""
import os
import sys
import traceback
from math import pi

import FreeCAD as App
import FreeCADGui as Gui
try:
    from PySide import QtWidgets
except ImportError:
    from PySide2 import QtWidgets
from pivy import coin

ROOT = "/workspace"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
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


def save_png(view, path, width=1280, height=720, state="capture"):
    """Render only the 3D view so README images are unobstructed model evidence."""
    view.saveImage(path, width, height, "White")
    if not os.path.isfile(path) or os.path.getsize(path) < 5000:
        raise RuntimeError("failed or suspiciously small screenshot: %s" % path)
    with open(path, "rb") as handle:
        header = handle.read(24)
    if header[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError("invalid PNG capture for %s" % state)
    rendered_width = int.from_bytes(header[16:20], "big")
    rendered_height = int.from_bytes(header[20:24], "big")
    if (rendered_width, rendered_height) != (width, height):
        raise RuntimeError(
            "invalid rendered dimensions for %s: %sx%s"
            % (state, rendered_width, rendered_height)
        )
    log("screenshot=%s state=%s bytes=%d" % (path, state, os.path.getsize(path)))


def avatar_center(avatar):
    """Return a stable center point for orbiting the camera around the mesh."""
    bbox = avatar.Mesh.BoundBox
    return App.Vector(
        0.5 * (bbox.XMin + bbox.XMax),
        0.5 * (bbox.YMin + bbox.YMax),
        0.5 * (bbox.ZMin + bbox.ZMax),
    )


def render_turntable(view, center, frame_dir, frame_count=72):
    """Render a complete 360-degree horizontal camera orbit around the avatar."""
    os.makedirs(frame_dir, exist_ok=True)
    view.setCameraType("Orthographic")
    view.viewRear()
    view.fitAll()
    view.zoomIn()
    events()

    camera = view.getCameraNode()
    center_coin = coin.SbVec3f(center.x, center.y, center.z)
    base_position = coin.SbVec3f(camera.position.getValue())
    base_offset = base_position - center_coin
    radius = base_offset.length()
    if radius <= 0:
        raise RuntimeError("avatar turntable camera radius is zero")

    up = coin.SbVec3f(0.0, 0.0, 1.0)
    camera.pointAt(center_coin, up)
    log("turntable-start frames=%d radius=%.4f" % (frame_count, radius))

    for frame in range(frame_count):
        angle = 2.0 * pi * frame / frame_count
        rotation = coin.SbRotation(coin.SbVec3f(0.0, 0.0, 1.0), angle)
        camera.position = rotation.multVec(base_offset) + center_coin
        camera.pointAt(center_coin, up)
        events()
        path = os.path.join(frame_dir, "frame-%03d.png" % frame)
        save_png(view, path, 640, 480, "Avatar turntable frame %03d" % frame)

    # Render the first frame once more as the final frame so the GIF loops cleanly
    # without a visible half-step at the seam.
    camera.position = base_position
    camera.pointAt(center_coin, up)
    events()
    closing_path = os.path.join(frame_dir, "frame-%03d.png" % frame_count)
    save_png(view, closing_path, 640, 480, "Avatar turntable closing frame")
    log("turntable-pass frames=%d" % (frame_count + 1))


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

        directions = (
            ("front", "viewRear"),
            ("rear", "viewFront"),
            ("left", "viewLeft"),
            ("right", "viewRight"),
            ("top", "viewTop"),
            ("bottom", "viewBottom"),
        )
        for direction, method_name in directions:
            getattr(view, method_name)()
            zoom_for_direction(view, direction)
            save_png(
                view,
                os.path.join(OUT, "cloth-avatar-%s.png" % direction),
                1280,
                720,
                "Avatar audit %s" % direction,
            )

        center = avatar_center(avatar)
        render_turntable(
            view,
            center,
            os.path.join(OUT, "cloth-avatar-turntable-frames"),
            frame_count=72,
        )
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
