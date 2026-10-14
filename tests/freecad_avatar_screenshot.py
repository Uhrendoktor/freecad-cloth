"""Deterministic avatar visual audit plus a full 360-degree turntable render."""

import os
import sys
import time
import traceback
from math import pi
from pathlib import Path

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
TURNTABLE_FRAMES = max(12, min(72, int(os.environ.get("CLOTH_TURNTABLE_FRAMES", "72"))))


def log(message):
    with open(LOG, "a", encoding="utf-8") as handle:
        handle.write(message + "\n")


def events():
    Gui.updateGui()
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.processEvents()


def wait_for_gui_ready(timeout_seconds=15.0):
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        window = Gui.getMainWindow()
        if window is not None and window.isVisible():
            window.show()
            events()
            return window
        events()
        time.sleep(0.05)
    raise RuntimeError(f"FreeCAD GUI did not become visible within {timeout_seconds:.1f}s")


def hide_task_docks(window):
    """Keep GUI chrome available for the audit but do not rely on it for captures."""
    hidden = []
    for dock in window.findChildren(QtWidgets.QDockWidget):
        title = str(dock.windowTitle()).strip().lower()
        if "task" in title:
            dock.hide()
            hidden.append(str(dock.windowTitle()))
    if hidden:
        log("hidden-task-docks={}".format(",".join(hidden)))
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
        raise RuntimeError(f"failed or suspiciously small screenshot: {path}")
    with open(path, "rb") as handle:
        header = handle.read(24)
    if header[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError(f"invalid PNG capture for {state}")
    rendered_width = int.from_bytes(header[16:20], "big")
    rendered_height = int.from_bytes(header[20:24], "big")
    if (rendered_width, rendered_height) != (width, height):
        raise RuntimeError(
            f"invalid rendered dimensions for {state}: {rendered_width}x{rendered_height}"
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


def render_body_shape_gallery(doc, view, avatar, output):
    """Render real HM08 mannequin examples at one orthographic scale."""
    from PIL import Image, ImageDraw, ImageFont

    from freecad_cloth.avatar.AvatarCommands import _rebuild
    from freecad_cloth.avatar.AvatarModel import DEFAULT_MEASUREMENTS, AvatarParameters, Pose

    measurement_fields = (
        "height",
        "shoulder",
        "chest",
        "underbust",
        "waist",
        "high_hip",
        "hip",
        "upper_arm",
        "thigh",
    )
    profile_rows = (
        (
            "Feminine form",
            0.15,
            0.55,
            (1680, 420, 930, 810, 720, 900, 1030, 290, 535),
        ),
        (
            "Masculine form",
            0.90,
            0.0,
            (1800, 490, 1030, 900, 850, 930, 1010, 330, 570),
        ),
        (
            "Slim",
            0.30,
            0.20,
            (1700, 390, 820, 720, 650, 800, 890, 250, 470),
        ),
        (
            "Plus-size",
            0.25,
            0.75,
            (1680, 470, 1220, 1090, 1170, 1220, 1350, 400, 710),
        ),
        (
            "Muscular",
            0.85,
            0.0,
            (1800, 550, 1150, 1050, 780, 890, 990, 430, 640),
        ),
        (
            "Tall",
            0.30,
            0.35,
            (1950, 440, 970, 835, 790, 900, 1010, 300, 550),
        ),
        (
            "Petite",
            0.25,
            0.35,
            (1530, 415, 900, 790, 710, 860, 970, 285, 520),
        ),
    )
    profiles = tuple(
        {
            "name": name,
            "gender": gender,
            "breast_size": breast_size,
            "measurements": dict(zip(measurement_fields, values, strict=True)),
        }
        for name, gender, breast_size, values in profile_rows
    )

    # The main six-side audit uses CAD edge lines; the gallery should compare silhouettes.
    avatar.ViewObject.DisplayMode = "Shaded"
    avatar.ViewObject.ShapeColor = (0.72, 0.72, 0.72)
    doc.recompute()

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame_dir = output_path.parent / ".avatar-body-shape-gallery-frames"
    frame_dir.mkdir(parents=True, exist_ok=True)

    # Fit the camera once, then preserve the orthographic scale for all seven
    # variations so tall/short and slim/plus-size silhouettes remain comparable.
    view.setCameraType("Orthographic")
    view.viewRear()
    view.fitAll()
    events()
    camera = view.getCameraNode()
    initial = avatar.Mesh.BoundBox
    initial_center = App.Vector(
        0.5 * (initial.XMin + initial.XMax),
        0.5 * (initial.YMin + initial.YMax),
        0.5 * (initial.ZMin + initial.ZMax),
    )
    center_coin = coin.SbVec3f(initial_center.x, initial_center.y, initial_center.z)
    base_position = coin.SbVec3f(camera.position.getValue())
    base_offset = base_position - center_coin
    camera_height = 1550.0
    camera.height = camera_height

    frames = []
    from freecad_cloth.avatar import AnnyAvatarBackend as anny_backend

    original_fit_steps = anny_backend._FIT_STEPS
    anny_backend._FIT_STEPS = min(original_fit_steps, 18)
    gallery_started = time.monotonic()
    log(
        "body-shape-gallery-start profiles=%d fit_steps=%d"
        % (len(profiles), anny_backend._FIT_STEPS)
    )
    try:
        for index, profile in enumerate(profiles):
            profile_started = time.monotonic()
            log(
                "body-shape-gallery-profile-start index=%d name=%s"
                % (index, profile["name"])
            )
            measurements = dict(DEFAULT_MEASUREMENTS)
            measurements.update(profile["measurements"])
            params = AvatarParameters(
                measurements,
                float(getattr(avatar, "SkinOffset", 3.0)),
                Pose("standing"),
                3,
                float(profile["gender"]),
                float(profile["breast_size"]),
            )
            _rebuild(avatar, params=params)
            log(
                "body-shape-gallery-profile-fit index=%d name=%s elapsed_ms=%.1f"
                % (index, profile["name"], 1000.0 * (time.monotonic() - profile_started))
            )
            # Rebuild reapplies the application's CAD wireframe style; use solid
            # shading for this silhouette comparison only.
            avatar.ViewObject.DisplayMode = "Shaded"
            avatar.ViewObject.ShapeColor = (0.72, 0.72, 0.72)
            if hasattr(avatar.ViewObject, "SpecularColor"):
                avatar.ViewObject.SpecularColor = (0.15, 0.15, 0.15)
            if hasattr(avatar.ViewObject, "Shininess"):
                avatar.ViewObject.Shininess = 5.0
            avatar.Label = "Avatar example: " + profile["name"]
            doc.recompute()

            bounds = avatar.Mesh.BoundBox
            center = App.Vector(
                0.5 * (bounds.XMin + bounds.XMax),
                0.5 * (bounds.YMin + bounds.YMax),
                0.5 * (bounds.ZMin + bounds.ZMax),
            )
            target = coin.SbVec3f(center.x, center.y, center.z)
            camera.position = target + base_offset
            camera.pointAt(target, coin.SbVec3f(0.0, 0.0, 1.0))
            camera.height = camera_height
            events()

            frame_path = frame_dir / ("%02d.png" % index)
            view.saveImage(str(frame_path), 420, 560, "White")
            if not frame_path.is_file() or frame_path.stat().st_size < 3000:
                raise RuntimeError(
                    "body-shape frame missing or suspiciously small: " + str(frame_path)
                )
            with Image.open(frame_path) as source:
                if source.size != (420, 560):
                    raise RuntimeError("body-shape frame has unexpected size: " + repr(source.size))
                frames.append(source.convert("RGB").copy())
            log(
                "body-shape-gallery-profile-pass index=%d name=%s elapsed_ms=%.1f"
                % (index, profile["name"], 1000.0 * (time.monotonic() - profile_started))
            )

    finally:
        anny_backend._FIT_STEPS = original_fit_steps

    def font(size, bold=False):
        """Load a readable annotation font with a portable fallback."""
        candidates = (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        )
        for candidate in candidates:
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
        return ImageFont.load_default()

    panel_width = 420
    image_height = 560
    label_height = 90
    panel_height = image_height + label_height
    gutter = 20
    margin = 28
    title_height = 106
    columns = 4
    canvas_width = margin * 2 + columns * panel_width + (columns - 1) * gutter
    canvas_height = title_height + 2 * panel_height + gutter + margin
    gallery = Image.new("RGB", (canvas_width, canvas_height), (244, 247, 251))
    draw = ImageDraw.Draw(gallery)
    draw.text((margin, 22), "Example mannequin body shapes", font=font(32, True), fill=(28, 43, 64))
    draw.text(
        (margin, 68),
        "Current HM08 mesh · shared orthographic scale · example measurement combinations",
        font=font(16),
        fill=(76, 91, 111),
    )

    for index, (profile, frame) in enumerate(zip(profiles, frames, strict=True)):
        row, column = divmod(index, columns)
        row_count = columns if row == 0 else len(profiles) - columns
        row_width = row_count * panel_width + (row_count - 1) * gutter
        row_start = (canvas_width - row_width) // 2
        x = row_start + column * (panel_width + gutter)
        y = title_height + row * (panel_height + gutter)
        draw.rounded_rectangle(
            (x, y, x + panel_width - 1, y + panel_height - 1),
            radius=12,
            fill=(255, 255, 255),
            outline=(214, 222, 232),
            width=2,
        )
        gallery.paste(frame, (x, y))
        label_y = y + image_height + 4
        draw.text(
            (x + panel_width // 2, label_y + 2),
            profile["name"],
            anchor="mt",
            font=font(21, True),
            fill=(28, 43, 64),
        )
        measurements = profile["measurements"]
        detail = "Height %d cm  ·  waist %d cm  ·  hip %d cm" % (
            round(measurements["height"] / 10),
            round(measurements["waist"] / 10),
            round(measurements["hip"] / 10),
        )
        draw.text(
            (x + panel_width // 2, label_y + 32),
            detail,
            anchor="mt",
            font=font(14),
            fill=(76, 91, 111),
        )
        control_detail = "Gender blend %d%%  ·  breast fullness %d%%" % (
            round(float(profile["gender"]) * 100),
            round(float(profile["breast_size"]) * 100),
        )
        draw.text(
            (x + panel_width // 2, label_y + 55),
            control_detail,
            anchor="mt",
            font=font(13),
            fill=(94, 109, 127),
        )

    gallery.save(output_path, format="PNG", optimize=True)
    if output_path.stat().st_size < 20000:
        raise RuntimeError("body-shape gallery is suspiciously small")
    from freecad_cloth.common.VisualCaptureValidation import validate_png_capture

    metrics = validate_png_capture(
        output_path,
        expected_width=canvas_width,
        expected_height=canvas_height,
        min_nonwhite_pixels=10000,
        min_distinct_rgb=16,
        min_opaque_pixels=10000,
    )
    log(
        "body-shape-gallery-pass profiles=%d elapsed_ms=%.1f bytes=%d"
        % (len(profiles), 1000.0 * (time.monotonic() - gallery_started), output_path.stat().st_size)
    )
    log(
        "body-shape-gallery=%s profiles=%d size=%dx%d bytes=%d distinct_rgb=%d"
        % (
            output_path,
            len(profiles),
            canvas_width,
            canvas_height,
            output_path.stat().st_size,
            metrics["distinct_rgb"],
        )
    )


def main():
    log("avatar-script-start")
    mode = os.environ.get("CLOTH_AVATAR_SCREENSHOT_MODE", "all").strip().lower()
    if mode not in ("all", "turntable", "gallery"):
        raise RuntimeError("CLOTH_AVATAR_SCREENSHOT_MODE must be all, turntable, or gallery")
    log("avatar-script-mode=%s" % mode)
    window = wait_for_gui_ready()

    init_gui = os.path.join(ROOT, "InitGui.py")
    with open(init_gui, encoding="utf-8") as handle:
        exec(compile(handle.read(), init_gui, "exec"), globals(), globals())
    events()
    hide_task_docks(window)

    from freecad_cloth.avatar.AvatarCommands import create_avatar

    doc = App.newDocument("ClothAvatarVisualAudit")
    try:
        avatar = create_avatar(attach_collision=False, doc=doc)
        if str(getattr(avatar, "AvatarStatus", "")) != "Valid":
            raise RuntimeError("avatar provider did not produce a valid mesh")
        if (
            int(getattr(avatar, "MeshVertexCount", 0)) <= 100
            or int(getattr(avatar, "MeshTriangleCount", 0)) <= 100
        ):
            raise RuntimeError("avatar visual fixture does not contain a real humanoid mesh")
        avatar.ViewObject.DisplayMode = "Flat Lines"
        avatar.ViewObject.ShapeColor = (0.72, 0.72, 0.72)
        avatar.ViewObject.LineColor = (0.20, 0.20, 0.20)
        avatar.ViewObject.LineWidth = 1.0
        doc.recompute()

        view = Gui.activeDocument().activeView()
        view.setAnimationEnabled(False)

        if mode in ("all", "turntable"):
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
                    os.path.join(OUT, f"cloth-avatar-{direction}.png"),
                    1280,
                    720,
                    f"Avatar audit {direction}",
                )

            center = avatar_center(avatar)
            render_turntable(
                view,
                center,
                os.path.join(OUT, "cloth-avatar-turntable-frames"),
                frame_count=TURNTABLE_FRAMES,
            )
        if mode in ("all", "gallery"):
            render_body_shape_gallery(
                doc,
                view,
                avatar,
                os.path.join(OUT, "avatar-body-shape-gallery.png"),
            )
        log("avatar-script-pass mode=%s" % mode)
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
    print(f"AVATAR SCREENSHOT FAILURE: {error!r}", flush=True)
    print(traceback.format_exc(), flush=True)
    log(f"avatar-script-fail exception={error!r}")
    os._exit(1)
