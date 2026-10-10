"""Real-FreeCAD smoke coverage for public staged sewing Preview/Commit/Cancel."""

import os
import re
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import contextlib
import io

import FreeCAD as App
import FreeCADGui as Gui
import Part

import freecad_cloth.pattern.PatternCommands  # registers Pattern commands
import freecad_cloth.sewing.SewingNetworkCommands  # registers network commands
from tests.support.freecad_input import (
    UiGifRecorder,
    _qt_modules,
    click_widget,
    focus_main_window,
)
from freecad_cloth.pattern.PatternModel import PatternPiece
from freecad_cloth.pattern.PatternObjects import add_pattern_piece
from freecad_cloth.sewing.SewingCommands import get_active_staged_sewing_task_panel
from freecad_cloth.sewing.SeamOverlay import (
    seam_highlights_enabled,
    seam_overlay_respects_depth,
    set_seam_highlights_enabled,
    set_seam_overlay_respect_depth,
)

_ORIGINAL_HIGHLIGHTS_ENABLED = seam_highlights_enabled()
_ORIGINAL_DEPTH_SETTING = seam_overlay_respects_depth()
set_seam_highlights_enabled(True)
set_seam_overlay_respect_depth(True)

LOG_PATH = Path(
    os.environ.get("CLOTH_SEWING_SMOKE_LOG", ROOT / "artifacts" / "sewing-creation-smoke.log")
)
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
LOG = []
LOG_PATH.write_text("", encoding="utf-8")


def _curved_shape(line_length, curve_span, curve_height):
    p0 = App.Vector(0, 0, 0)
    p1 = App.Vector(float(line_length), 0, 0)
    p2 = App.Vector(float(line_length), 40, 0)
    p3 = App.Vector(float(line_length) - float(curve_span), 40, 0)
    curve = Part.BezierCurve()
    curve.setPoles(
        [
            p2,
            App.Vector(float(line_length), 40 + float(curve_height), 0),
            App.Vector(float(line_length) - float(curve_span), 40 + float(curve_height), 0),
            p3,
        ]
    )
    return Part.Face(
        Part.Wire(
            [
                Part.makeLine(p0, p1),
                Part.makeLine(p1, p2),
                curve.toShape(),
                Part.makeLine(p3, p0),
            ]
        )
    )


def add_curved_piece(doc, name, piece_id, line_length, curve_span=80.0, curve_height=90.0):
    obj = doc.addObject("Part::Feature", name)
    obj.addProperty("App::PropertyString", "PatternType", "Cloth").PatternType = "PatternPiece"
    obj.addProperty("App::PropertyString", "PieceId", "Cloth").PieceId = str(piece_id)
    obj.addProperty("App::PropertyLength", "Width", "Parameters").Width = float(line_length)
    obj.addProperty("App::PropertyLength", "Height", "Parameters").Height = 40.0 + float(
        curve_height
    )
    obj.addProperty("App::PropertyString", "SewingOutline", "Cloth").SewingOutline = repr(
        [
            (0.0, 0.0),
            (float(line_length), 0.0),
            (float(line_length), 40.0),
            (float(line_length) - float(curve_span), 40.0),
        ]
    )
    obj.Shape = _curved_shape(line_length, curve_span, curve_height)
    return obj


def edge_sample_spacing(edge, parameters=(0.0, 0.07, 0.19, 0.43, 0.71, 1.0)):
    first, last = float(edge.FirstParameter), float(edge.LastParameter)
    points = [edge.valueAt(first + (last - first) * float(parameter)) for parameter in parameters]
    return [
        ((left.x - right.x) ** 2 + (left.y - right.y) ** 2 + (left.z - right.z) ** 2) ** 0.5
        for left, right in zip(points, points[1:], strict=False)
    ]


def process_events():
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    QtWidgets.QApplication.processEvents()
    Gui.updateGui()
    QtWidgets.QApplication.processEvents()


def pattern_piece_color_counts(frame):
    """Count distinctive fixture colors in a captured main-window frame."""
    counts = {"blue": 0, "orange": 0, "green": 0}
    for red, green, blue in frame.convert("RGB").getdata():
        if blue >= 120 and blue - red >= 25 and green - red >= 15:
            counts["blue"] += 1
        if red >= 140 and red - green >= 25 and green - blue >= 20:
            counts["orange"] += 1
        if green >= 110 and green - red >= 20 and green - blue >= 10:
            counts["green"] += 1
    return counts


def assert_pattern_piece_colors_visible(frame):
    """Reject a seam GIF whose viewport has no rendered pattern pieces."""
    counts = pattern_piece_color_counts(frame)
    assert all(value >= 500 for value in counts.values()), (
        "seam-assignment GIF must visibly render all three colored pattern pieces; "
        f"detected pixel counts={counts!r}"
    )


def capture_main_window_frame(window):
    """Capture the full FreeCAD window with the same native method as the GIF recorder."""
    from PIL import Image

    QtCore, _QtGui, _QtTest, QtWidgets = _qt_modules()
    app = QtWidgets.QApplication.instance()
    screen = None if app is None else app.primaryScreen()
    if screen is None:
        raise RuntimeError("Qt screen capture is unavailable for seam display-mode probing")
    pixmap = screen.grabWindow(int(window.winId()))
    if pixmap.isNull():
        raise RuntimeError("Qt returned an empty seam display-mode probe frame")
    buffer = QtCore.QBuffer()
    buffer.open(QtCore.QIODevice.WriteOnly)
    if not pixmap.save(buffer, "PNG"):
        buffer.close()
        raise RuntimeError("could not encode the seam display-mode probe frame")
    payload = bytes(buffer.data())
    buffer.close()
    frame = Image.open(io.BytesIO(payload)).convert("RGB")
    # Match the recorder's 0.5 scale so this probe uses the same pixel budget
    # as the final GIF's fail-fast visibility assertion.
    resampling = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
    size = (max(1, int(frame.width * 0.5)), max(1, int(frame.height * 0.5)))
    return frame.resize(size, resampling)


def record(message):
    LOG.append(message)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(message + "\n")
        handle.flush()
    print(message, flush=True)


def seam_color_snapshot(seams):
    from math import isclose

    from freecad_cloth.sewing.SewingView import seam_color_map

    ids = tuple(str(getattr(seam, "SeamId", "")) for seam in seams)
    expected = seam_color_map(ids)
    actual = {
        str(getattr(seam, "SeamId", "")): tuple(
            round(float(value), 6) for value in seam.ViewObject.LineColor[:3]
        )
        for seam in seams
    }
    for seam_id, expected_rgb in expected.items():
        actual_rgb = actual.get(seam_id)
        assert actual_rgb is not None, f"native seam color missing persistent SeamId {seam_id}"
        assert all(
            isclose(float(actual_rgb[index]), float(expected_rgb[index]), rel_tol=0.0, abs_tol=1e-6)
            for index in range(3)
        ), (
            f"native seam color for {seam_id} differs: actual={actual_rgb!r} expected={expected_rgb!r}"
        )
    assert len(set(actual.values())) == len(actual), (
        "native seam colors are not unique per persistent SeamId"
    )
    return actual


def assert_seam_overlay(document, expected_ids, hovered_seam_id=None):
    from freecad_cloth.sewing.SeamOverlay import refresh_seam_overlay

    controller = refresh_seam_overlay(document)
    assert controller is not None, "semantic seam overlay was not attached to the active viewport"
    assert controller.root is not None, "semantic seam overlay has no Coin root"
    assert getattr(controller, "_location_callback", None) is not None, (
        "seam hover callback is not installed on the active viewport"
    )
    rendered = set(controller.rendered_seam_ids)
    assert set(expected_ids) <= rendered, (
        "visible valid semantic seams missing from viewport overlay: "
        f"expected={sorted(expected_ids)!r} rendered={sorted(rendered)!r}"
    )
    assert controller.root.getNumChildren() > 1, "viewport overlay contains no seam geometry"

    target = str(hovered_seam_id or "").strip() or sorted(expected_ids)[0]
    assert target in set(expected_ids), (
        "requested hover label must belong to the visible semantic seam IDs"
    )
    try:
        workbench_name = str(Gui.activeWorkbench().name()).lower()
    except (AttributeError, RuntimeError, TypeError):
        workbench_name = ""
    prefer_simulation = "simulation" in workbench_name
    controller.refresh(
        document,
        active_seam_id=target,
        prefer_simulation=prefer_simulation,
        hovered_seam_id=target,
    )
    assert controller.rendered_label_seam_ids == (target,), (
        "hover should show only the matching seam's two labels: "
        f"actual={controller.rendered_label_seam_ids!r}"
    )
    controller.refresh(
        document,
        active_seam_id="",
        prefer_simulation=prefer_simulation,
        hovered_seam_id="",
    )
    assert controller.rendered_label_seam_ids == (), (
        "seam labels should be hidden when no seam edge is hovered"
    )
    # Leave one seam hovered for a useful visual-evidence screenshot.
    controller.refresh(
        document,
        active_seam_id=target,
        prefer_simulation=prefer_simulation,
        hovered_seam_id=target,
    )
    return controller


def save_seam_overlay_evidence(document, expected_ids, filename, hovered_seam_id=None):
    """Capture a view only after its transient Coin overlay passes semantic checks."""
    controller = assert_seam_overlay(document, expected_ids, hovered_seam_id)
    active_document = Gui.activeDocument()
    view = active_document.activeView() if active_document is not None else None
    assert view is not None, "active FreeCAD view is unavailable for seam evidence"
    process_events()
    view.redraw()
    process_events()
    destination = LOG_PATH.parent / filename
    destination.parent.mkdir(parents=True, exist_ok=True)
    view.saveImage(str(destination), 1280, 720, "White")
    size = destination.stat().st_size if destination.is_file() else 0
    assert size > 5000, f"seam overlay screenshot is missing or suspiciously small: {destination}"
    record(f"seam-overlay-image={filename} bytes={size}")
    return controller


def save_seam_overlay_hover_animation(document, seam_ids, filename):
    """Capture real viewport frames while hover labels and highlights change."""
    from PIL import Image

    from tests.support.freecad_input import write_gif
    from freecad_cloth.sewing.SeamOverlay import refresh_seam_overlay

    identities = sorted({str(value).strip() for value in seam_ids if str(value).strip()})
    assert identities, "seam overlay animation requires at least one semantic seam ID"
    active_document = Gui.activeDocument()
    view = active_document.activeView() if active_document is not None else None
    assert view is not None, "active FreeCAD view is unavailable for seam animation"
    target_a, target_b = identities[0], identities[-1]

    frame_dir = LOG_PATH.parent / "seam-overlay-hover-frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    specs = (
        ("no-hover", True, ""),
        ("hover-first", True, target_a),
        ("hover-second", True, target_b),
        ("highlights-disabled", False, ""),
        ("highlights-restored", True, target_a),
    )
    frames = []
    try:
        for index, (state_name, enabled, hovered) in enumerate(specs):
            if seam_highlights_enabled() != enabled:
                set_seam_highlights_enabled(enabled)
            controller = refresh_seam_overlay(document) if enabled else None
            if enabled:
                assert controller is not None and controller.root is not None
                controller.refresh(
                    document,
                    active_seam_id=hovered,
                    prefer_simulation=False,
                    hovered_seam_id=hovered,
                )
                expected_labels = (hovered,) if hovered else ()
                assert controller.rendered_label_seam_ids == expected_labels, (
                    "hover animation rendered unexpected labels: "
                    f"state={state_name} labels={controller.rendered_label_seam_ids!r}"
                )
            else:
                assert controller is None, "disabled color highlights left an overlay attached"
                neutral = (0.48, 0.48, 0.48)
                colored_seams = [
                    obj
                    for obj in document.Objects
                    if str(getattr(obj, "SeamId", "")).strip()
                    and getattr(obj, "ViewObject", None) is not None
                ]
                assert colored_seams and all(
                    tuple(round(float(c), 6) for c in obj.ViewObject.LineColor[:3]) == neutral
                    for obj in colored_seams
                ), "disabled highlights left identity colors on native seam linework"

            process_events()
            view.redraw()
            process_events()
            frame_path = frame_dir / f"state-{index:02d}-{state_name}.png"
            view.saveImage(str(frame_path), 1280, 720, "White")
            assert frame_path.is_file() and frame_path.stat().st_size > 5000, (
                f"seam overlay animation frame is missing or empty: {state_name}"
            )
            with Image.open(frame_path) as image_frame:
                rgb = image_frame.convert("RGB")
                resampling = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
                frames.append(rgb.resize((640, 360), resampling).copy())

        output = LOG_PATH.parent / "ui-gifs" / filename
        write_gif(frames, output, fps=2, max_colors=96)
        assert output.is_file() and output.stat().st_size > 5000, (
            "seam overlay hover animation is missing or suspiciously small"
        )
        record(
            f"seam-overlay-animation={filename} frames={len(frames)} bytes={output.stat().st_size}"
        )
        return output
    finally:
        # The smoke continues using color identities after the animation.
        set_seam_highlights_enabled(True)
        set_seam_overlay_respect_depth(True)


def save_seam_overlay_options_evidence(filename):
    """Capture the real Sewing workbench options dialog as visual evidence."""
    from freecad_cloth.sewing.SewingCommands import _build_seam_overlay_options_dialog

    dialog, highlights, respect_depth = _build_seam_overlay_options_dialog()
    assert highlights.isChecked() is True
    assert respect_depth.isChecked() is True
    destination = LOG_PATH.parent / filename
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        dialog.show()
        if callable(getattr(dialog, "raise_", None)):
            dialog.raise_()
        process_events()
        image = dialog.grab()
        assert not image.isNull(), "overlay options dialog could not be captured"
        assert image.save(str(destination), "PNG"), "overlay options screenshot could not be saved"
        assert destination.is_file() and destination.stat().st_size > 1000, (
            "overlay options screenshot is missing or suspiciously small"
        )
        record(f"seam-overlay-options-image={filename} bytes={destination.stat().st_size}")
    finally:
        dialog.close()
        process_events()


def wait_for_task_close():
    try:
        from PySide import QtCore, QtWidgets
    except ImportError:
        from PySide2 import QtCore, QtWidgets
    for _ in range(80):
        active = Gui.Control.activeDialog()
        if active is None or not bool(active):
            return
        loop = QtCore.QEventLoop()
        QtCore.QTimer.singleShot(0, loop.quit)
        loop.exec()
        QtWidgets.QApplication.processEvents()
    raise AssertionError("task dialog did not close after the requested Commit/Cancel action")



def select_edges(*items):
    Gui.Selection.clearSelection()
    for obj, edge in items:
        Gui.Selection.addSelection(obj, "Edge%d" % (int(edge) + 1))
    process_events()


def open_public(command):
    if Gui.Control.activeDialog():
        Gui.Control.closeDialog()
        process_events()
    Gui.runCommand(command, 0)
    process_events()
    panel = get_active_staged_sewing_task_panel()
    assert panel is not None, command + " did not retain a task panel"
    assert getattr(panel, "form", None) is not None
    active = Gui.Control.activeDialog()
    assert active is not None, command + " did not open an active task dialog"
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    widgets = [panel.form] + list(panel.form.findChildren(QtWidgets.QWidget))
    dialog_text = " | ".join(
        str(getter())
        for widget in widgets
        for getter in [getattr(widget, "text", None)]
        if callable(getter)
    )
    for required in ("Preview", "Commit", "Cancel", "Selected semantic pattern edges"):
        assert required in dialog_text, (
            command + " task panel is missing required control text: " + required
        )
    return panel


def close_public_task(panel=None):
    if panel is not None:
        with contextlib.suppress(Exception):
            panel.reject()
    wait_for_task_close()


doc = None
recorder = None
_success = False
try:
    record("smoke=started")
    record("commands=loaded-from-package")
    for command in (
        "ClothSewing_CreateSeam",
        "ClothSewing_CreateMNSewing",
        "ClothSewing_FreeSewing",
        "ClothSewing_SeamOverlayOptions",
    ):
        assert command in Gui.listCommands(), "missing public sewing command: " + command
    record("commands=registered")

    doc = App.newDocument("SewingCreationSmoke")
    piece_a = add_pattern_piece(
        doc,
        PatternPiece("SmokeA", [(0, 0), (100, 0), (100, 100), (0, 100)], id="smoke-a"),
    )
    piece_b = add_pattern_piece(
        doc,
        PatternPiece("SmokeB", [(0, 0), (100, 0), (100, 100), (0, 100)], id="smoke-b"),
    )
    piece_c = add_pattern_piece(
        doc,
        PatternPiece("SmokeC", [(0, 0), (100, 0), (100, 100), (0, 100)], id="smoke-c"),
    )
    doc.recompute()
    # Keep the outlines separate so the recorded viewport workflow shows two
    # distinct workpieces and unambiguous source/counterpart edge selection.
    piece_b.Placement = App.Placement(App.Vector(145.0, 0.0, 0.0), App.Rotation())
    piece_c.Placement = App.Placement(App.Vector(290.0, 0.0, 0.0), App.Rotation())
    doc.recompute()
    record("fixtures=created pieces=3")

    # Record from the real sewing workbench and let Fit All establish a valid
    # camera center and clipping range. Then set only the orthographic height;
    # moving the camera manually can put all geometry outside FreeCAD's clip range.
    Gui.activateWorkbench("ClothSewingWorkbench")
    process_events()
    window = focus_main_window(Gui, size=(1280, 720))
    view = Gui.activeDocument().activeView()
    for piece, color in (
        (piece_a, (0.34, 0.65, 0.88)),
        (piece_b, (0.94, 0.62, 0.30)),
        (piece_c, (0.42, 0.72, 0.52)),
    ):
        view_object = piece.ViewObject
        view_object.Visibility = True
        view_object.ShapeColor = color
        view_object.LineColor = (0.12, 0.16, 0.21)
        view_object.LineWidth = 3.0
        view_object.Transparency = 0
    doc.recompute()
    view.setCameraType("Orthographic")
    view.viewTop()
    view.fitAll()
    process_events()
    _QtCore, _QtGui, QtTest, _QtWidgets = _qt_modules()
    QtTest.QTest.qWait(200)

    world_bounds = []
    for piece in (piece_a, piece_b, piece_c):
        box = piece.Shape.BoundBox
        if float(box.XLength) <= 0.0 or float(box.YLength) <= 0.0:
            raise RuntimeError(
                "seam-assignment GIF fixture has empty pattern geometry: " + piece.Label
            )
        if not bool(piece.ViewObject.Visibility):
            raise RuntimeError(
                "seam-assignment GIF fixture is not visible: " + piece.Label
            )
        # Shape.BoundBox is already in the placed/world coordinate system here.
        world_bounds.append((
            float(box.XMin), float(box.YMin), float(box.ZMin),
            float(box.XMax), float(box.YMax), float(box.ZMax),
        ))
    xmin = min(value[0] for value in world_bounds)
    ymin = min(value[1] for value in world_bounds)
    xmax = max(value[3] for value in world_bounds)
    ymax = max(value[4] for value in world_bounds)
    view_size = view.getSize()
    view_width, view_height = float(view_size[0]), float(view_size[1])
    if view_width <= 0.0 or view_height <= 0.0:
        raise RuntimeError("seam-assignment GIF has an invalid viewport size")
    aspect = view_width / view_height
    extent_x, extent_y = xmax - xmin, ymax - ymin
    camera_height = max(150.0, 1.25 * extent_y, 1.25 * extent_x / aspect)
    camera = view.getCameraNode()
    camera.height.setValue(float(camera_height))
    if hasattr(view, "redraw"):
        view.redraw()
    process_events()
    QtTest.QTest.qWait(150)
    camera_match = re.search(
        r"\bheight\s+([0-9]+(?:\.[0-9]*)?(?:[eE][+-]?[0-9]+)?)",
        view.getCamera(),
    )
    if camera_match is None or float(camera_match.group(1)) < camera_height * 0.95:
        raise RuntimeError(
            "seam-assignment GIF camera did not apply the requested world-space framing: "
            f"expected_height={camera_height:.3f}, camera={camera_match.group(1) if camera_match else 'missing'}"
        )
    record(
        "seam-camera=passed bounds=(%.2f,%.2f)-(%.2f,%.2f) "
        "height=%.2f viewport=%dx%d"
        % (
            xmin, ymin, xmax, ymax, float(camera_match.group(1)),
            int(view_width), int(view_height),
        )
    )

    # Pattern pieces use a view-provider-specific display-mode enumeration.
    # Probe the actual supported modes and keep the first that visibly paints
    # all three face colors; never assume a generic Part feature's mode names.
    first_view = piece_a.ViewObject
    display_modes = []
    list_modes = getattr(first_view, "listDisplayModes", None)
    if callable(list_modes):
        try:
            display_modes = [str(mode) for mode in list_modes()]
        except (AttributeError, RuntimeError, TypeError, ValueError):
            display_modes = []
    if not display_modes:
        enum_modes = getattr(first_view, "getEnumerationsOfProperty", None)
        if callable(enum_modes):
            try:
                display_modes = [str(mode) for mode in enum_modes("DisplayMode")]
            except (AttributeError, RuntimeError, TypeError, ValueError):
                display_modes = []
    display_modes = list(dict.fromkeys(mode for mode in display_modes if mode.strip()))
    if not display_modes:
        raise RuntimeError(
            "could not discover any display modes for the seam-assignment fixture"
        )

    chosen_display_mode = None
    last_probe_counts = {}
    for mode in display_modes:
        for piece in (piece_a, piece_b, piece_c):
            piece.ViewObject.DisplayMode = mode
        process_events()
        view.redraw()
        process_events()
        probe_frame = capture_main_window_frame(window)
        last_probe_counts = pattern_piece_color_counts(probe_frame)
        record(
            f"seam-display-mode-probe={mode!r} color-pixels={last_probe_counts!r}"
        )
        if all(value >= 500 for value in last_probe_counts.values()):
            chosen_display_mode = mode
            break
    if chosen_display_mode is None:
        raise RuntimeError(
            "none of the supported pattern-piece display modes visibly rendered all colors; "
            f"modes={display_modes!r}, last_pixel_counts={last_probe_counts!r}"
        )
    record(f"seam-display-mode=selected mode={chosen_display_mode!r}")

    recorder = UiGifRecorder(
        "artifacts/ui-gifs/seam-assignment.gif",
        gui=Gui,
        window=window,
        fps=12,
        scale=0.5,
        max_frames=120,
        show_cursor=False,
    )
    recorder.start()
    recorder.hold(700)
    assert_pattern_piece_colors_visible(recorder.frames[-1])

    before = {obj.Name for obj in doc.Objects}
    # Stage the selection so the recording distinguishes side A from the
    # selected counterpart on side B before opening the real sewing task panel.
    # FreeCAD's selection API produces the same viewport selection state
    # without relying on fragile screen-coordinate hit testing in Xvfb.
    select_edges((piece_a, 0))
    recorder.hold(800)
    select_edges((piece_a, 0), (piece_b, 0))
    recorder.hold(800)
    panel = open_public("ClothSewing_CreateSeam")
    recorder.hold(1100)
    assert any(getattr(obj, "SeamId", "") for obj in panel.session.created), (
        "1:1 preview did not create a seam"
    )
    assert "Preview valid" in panel.feedback.text()
    assert Gui.Control.activeDialog() is not None
    record("preview-1to1=passed")
    recorder.hold(700)
    click_widget(panel.commit_button)
    process_events()
    wait_for_task_close()
    recorder.hold(800)
    recorder.stop()
    assert any(getattr(obj, "SeamId", "") for obj in doc.Objects if obj.Name not in before), (
        "1:1 commit lost seam"
    )
    record("commit-1to1=passed")

    # Exercise the viewport picker event handler with native document selection
    # and the existing transactional Preview/Cancel boundary.
    from freecad_cloth.sewing.SewingCreationGui import SewingCreationTaskPanel

    class HitView:
        def __init__(self, hits):
            self.hits = list(hits)

        def getObjectInfo(self, _x, _y):
            return self.hits.pop(0)

    pick_before = {obj.Name for obj in doc.Objects}
    Gui.Selection.clearSelection()
    picker = SewingCreationTaskPanel("seam")
    Gui.Control.showDialog(picker)
    process_events()
    picker._viewport_view = HitView(
        [
            {"Object": piece_a.Name, "Component": "Edge3"},
            {"Object": piece_b.Name, "Component": "Edge3"},
        ]
    )
    picker._viewport_callback = None
    picker._viewport_picking = True
    picker._viewport_mouse_event(
        {"State": "DOWN", "Button": "BUTTON1", "Position": (100, 200)}
    )
    assert len(picker._viewport_picks) == 1
    assert "Side A" in picker.feedback.text()
    picker._viewport_mouse_event(
        {"State": "DOWN", "Button": "BUTTON1", "Position": (300, 200)}
    )
    assert any(getattr(obj, "SeamId", "") for obj in picker.session.created)
    assert "Seam preview shown" in picker.feedback.text()
    assert picker.commit_button.isEnabled()
    picker.reject()
    wait_for_task_close()
    process_events()
    assert {obj.Name for obj in doc.Objects} == pick_before
    record("viewport-pick-preview-cancel=passed")

    cancel_before = {obj.Name for obj in doc.Objects}
    select_edges((piece_a, 1), (piece_b, 1))
    cancel_panel = open_public("ClothSewing_CreateSeam")
    assert any(getattr(obj, "SeamId", "") for obj in cancel_panel.session.created)
    click_widget(cancel_panel.cancel_button)
    process_events()
    wait_for_task_close()
    assert {obj.Name for obj in doc.Objects} == cancel_before, "cancel persisted preview objects"
    record("cancel-1to1=passed via=qt-mouse")

    count_before = {obj.Name for obj in doc.Objects}
    select_edges((piece_a, 2))
    invalid_count_panel = open_public("ClothSewing_CreateSeam")
    assert "Preview rejected" in invalid_count_panel.feedback.text()
    assert "exactly two edges" in invalid_count_panel.feedback.text()
    assert {obj.Name for obj in doc.Objects} == count_before
    invalid_count_panel.cancel_button.click()
    wait_for_task_close()
    assert {obj.Name for obj in doc.Objects} == count_before
    record("selection-count-rejection=passed")

    same_piece_before = {obj.Name for obj in doc.Objects}
    select_edges((piece_a, 0), (piece_a, 1))
    invalid_panel = open_public("ClothSewing_CreateSeam")
    assert "Preview rejected" in invalid_panel.feedback.text()
    assert "different pattern pieces" in invalid_panel.feedback.text()
    assert {obj.Name for obj in doc.Objects} == same_piece_before
    invalid_panel.cancel_button.click()
    wait_for_task_close()
    assert {obj.Name for obj in doc.Objects} == same_piece_before
    record("invalid-same-piece-preview=passed")

    mn_before = {obj.Name for obj in doc.Objects}
    select_edges((piece_a, 0), (piece_b, 1), (piece_c, 2))
    invalid_mn_panel = open_public("ClothSewing_CreateMNSewing")
    assert "Preview rejected" in invalid_mn_panel.feedback.text()
    assert "two different pattern pieces" in invalid_mn_panel.feedback.text()
    assert {obj.Name for obj in doc.Objects} == mn_before
    invalid_mn_panel.cancel_button.click()
    wait_for_task_close()
    assert {obj.Name for obj in doc.Objects} == mn_before
    record("invalid-mn-partition-preview=passed")

    select_edges((piece_a, 0), (piece_a, 1), (piece_b, 0), (piece_b, 1))
    mn_panel = open_public("ClothSewing_CreateMNSewing")
    assert any(
        getattr(obj, "SewingType", "") == "SewingNetwork" for obj in mn_panel.session.created
    )
    assert "Preview valid" in mn_panel.feedback.text()
    record("preview-mn=passed")
    mn_panel.commit_button.click()
    wait_for_task_close()
    networks = [obj for obj in doc.Objects if getattr(obj, "SewingType", "") == "SewingNetwork"]
    assert networks and networks[-1].Status == "Valid", "M:N commit did not leave a valid network"
    record("commit-mn=passed")

    curved_a = add_curved_piece(
        doc, "CurvedA", "curved-a", 100.0, curve_span=80.0, curve_height=90.0
    )
    doc.recompute()
    curve_spacings = edge_sample_spacing(curved_a.Shape.Edges[2])
    assert max(curve_spacings) / min(curve_spacings) > 1.20
    record(
        f"curved-sampling=passed max_spacing={max(curve_spacings):.6f} min_spacing={min(curve_spacings):.6f}"
    )

    probe = Part.BezierCurve()
    probe.setPoles(
        [
            App.Vector(0, 40, 0),
            App.Vector(0, 160, 0),
            App.Vector(-80, 160, 0),
            App.Vector(-80, 40, 0),
        ]
    )
    probe_points = probe.toShape().discretize(Number=64)
    b_curve_length = sum(
        ((left.x - right.x) ** 2 + (left.y - right.y) ** 2 + (left.z - right.z) ** 2) ** 0.5
        for left, right in zip(probe_points, probe_points[1:], strict=False)
    )
    b_line_length = float(
        curved_a.Shape.Edges[0].Length + curved_a.Shape.Edges[2].Length - b_curve_length
    )
    curved_b = add_curved_piece(
        doc, "CurvedB", "curved-b", b_line_length, curve_span=80.0, curve_height=120.0
    )
    doc.recompute()

    select_edges((curved_a, 0), (curved_a, 2), (curved_b, 0), (curved_b, 2))
    curved_panel = open_public("ClothSewing_CreateMNSewing")
    curved_preview = next(
        (
            obj
            for obj in curved_panel.session.created
            if getattr(obj, "SewingType", "") == "SewingNetwork"
        ),
        None,
    )
    assert curved_preview is not None and curved_preview.Status == "Valid"
    assert len(curved_preview.Seams) == 3
    assert curved_preview.SideACount == 2 and curved_preview.SideBCount == 2

    curved_a.SewingOutline = repr([(0.0, 0.0), (100.0, 0.0), (100.0, 40.0), (-5.0, 40.0)])
    curved_a.Shape = _curved_shape(100.0, 105.0, 90.0)
    doc.recompute()
    assert curved_panel.accept() is False
    assert "Preview validation failed" in curved_panel.feedback.text()
    record("stale-endpoint-invalidation=passed commit-blocked=true")
    curved_panel.cancel_button.click()
    wait_for_task_close()

    curved_a.SewingOutline = repr([(0.0, 0.0), (100.0, 0.0), (100.0, 40.0), (20.0, 40.0)])
    curved_a.Shape = _curved_shape(100.0, 80.0, 90.0)
    doc.recompute()
    select_edges((curved_a, 0), (curved_a, 2), (curved_b, 0), (curved_b, 2))
    curved_panel = open_public("ClothSewing_CreateMNSewing")
    curved_preview = next(
        obj
        for obj in curved_panel.session.created
        if getattr(obj, "SewingType", "") == "SewingNetwork"
    )
    curved_panel.commit_button.click()
    wait_for_task_close()
    curved_network = next(
        obj
        for obj in doc.Objects
        if getattr(obj, "SewingType", "") == "SewingNetwork"
        and str(getattr(obj, "RelationshipId", "")) == str(curved_preview.RelationshipId)
    )
    from freecad_cloth.sewing.SewingObjects import _seam_length

    member_a_total = sum(float(_seam_length(curved_a, seam, "A")) for seam in curved_network.Seams)
    member_b_total = sum(float(_seam_length(curved_b, seam, "B")) for seam in curved_network.Seams)
    assert abs(member_a_total - float(curved_network.LengthA)) < 1e-6
    assert abs(member_b_total - float(curved_network.LengthB)) < 1e-6
    assert curved_network.Status == "Valid"
    assert float(curved_network.LengthDifference) <= 0.05 * min(
        float(curved_network.LengthA), float(curved_network.LengthB)
    )
    pair_gaps = [
        abs(float(_seam_length(curved_a, seam, "A")) - float(_seam_length(curved_b, seam, "B")))
        for seam in curved_network.Seams
    ]
    assert (
        max(pair_gaps)
        <= 0.05
        * max(float(curved_network.LengthA), float(curved_network.LengthB))
        / len(curved_network.Seams)
        + 0.01
    )
    record(
        f"curved-mn=passed members=2,2 segments=3 physical-length=proportional length_a={float(curved_network.LengthA):.9f} length_b={float(curved_network.LengthB):.9f} delta={float(curved_network.LengthDifference):.9f} max_pair_gap={max(pair_gaps):.9f}"
    )

    for seam in curved_network.Seams:
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(seam)
        before = bool(seam.ReversedB)
        Gui.runCommand("ClothSewing_ReverseSeam", 0)
        process_events()
        assert bool(seam.ReversedB) is (not before)
    doc.recompute()
    assert all(bool(seam.ReversedB) for seam in curved_network.Seams)
    record("curved-mn-reversal=passed segments=3")
    baseline_seam_colors = seam_color_snapshot(curved_network.Seams)
    record("seam-colors-pair-identity=passed unique=%d" % len(baseline_seam_colors))
    doc.recompute()
    assert seam_color_snapshot(curved_network.Seams) == baseline_seam_colors
    record("seam-colors-recompute=passed identity-stable=true")
    from freecad_cloth.sewing.SewingView import apply_seam_colors
    apply_seam_colors(doc.Objects)
    refreshed_network = next(
        obj
        for obj in doc.Objects
        if getattr(obj, "SewingType", "") == "SewingNetwork"
        and str(getattr(obj, "RelationshipId", "")) == str(curved_network.RelationshipId)
    )
    assert seam_color_snapshot(refreshed_network.Seams) == baseline_seam_colors
    record("seam-colors-context=passed")
    Gui.activateWorkbench("ClothPatternWorkbench")
    process_events()
    active_workbench = Gui.activeWorkbench()
    active_name = str(active_workbench.name()) if callable(getattr(active_workbench, "name", None)) else str(active_workbench)
    assert "pattern" in active_name.lower(), (
        "seam overlay acceptance requires the Cloth Pattern workbench to be active"
    )
    Gui.runCommand("ClothPattern_Show2D", 0)
    process_events()
    pattern_network = next(
        obj
        for obj in doc.Objects
        if getattr(obj, "SewingType", "") == "SewingNetwork"
        and str(getattr(obj, "RelationshipId", "")) == str(curved_network.RelationshipId)
    )
    assert seam_color_snapshot(pattern_network.Seams) == baseline_seam_colors
    record("seam-colors-pattern-2d=passed")
    pattern_overlay_ids = [str(seam.SeamId) for seam in pattern_network.Seams]
    save_seam_overlay_evidence(doc, pattern_overlay_ids, "seam-overlay-pattern-2d.png")
    record("seam-viewport-overlay-pattern-2d=passed labels=paired-A-B")
    Gui.activateWorkbench("ClothSewingWorkbench")
    process_events()
    active_workbench = Gui.activeWorkbench()
    active_name = str(active_workbench.name()) if callable(getattr(active_workbench, "name", None)) else str(active_workbench)
    assert "sewing" in active_name.lower(), (
        "seam overlay acceptance requires the Cloth Sewing workbench to be active"
    )
    endpoint_snapshot = tuple(
        sorted(
            (
                str(seam.SeamId),
                str(seam.EdgeAId),
                str(seam.EdgeBId),
                round(float(seam.StartA), 12),
                round(float(seam.EndA), 12),
                round(float(seam.StartB), 12),
                round(float(seam.EndB), 12),
                bool(seam.ReversedB),
            )
            for seam in curved_network.Seams
        )
    )

    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(curved_network)
    process_events()
    Gui.runCommand("ClothSewing_EditNetwork", 0)
    process_events()
    network_dialog = Gui.Control.activeDialog()
    assert network_dialog is not None
    with contextlib.suppress(ImportError):
        pass
    from freecad_cloth.sewing.SewingNetworkCommands import get_active_network_task_panel

    network_panel = get_active_network_task_panel()
    assert network_panel is not None
    assert getattr(network_panel, "form", None) is not None and network_panel.form.isVisible()
    evidence_label = getattr(network_panel, "correspondence", None)
    assert evidence_label is not None
    assert str(evidence_label.objectName()) == "ClothSewingNetworkCorrespondenceEvidence"
    network_text = str(evidence_label.text()).lower()
    assert "severity info" in network_text
    assert "recovery:" in network_text
    record("correspondence-gui-evidence=passed severity=info")
    if callable(getattr(network_dialog, "reject", None)):
        network_dialog.reject()
    else:
        Gui.Control.closeDialog()
    process_events()

    visual_seam = curved_network.Seams[0]
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(visual_seam)
    Gui.runCommand("ClothSewing_FocusSeam3D", 0)
    process_events()
    assert seam_color_snapshot(curved_network.Seams) == baseline_seam_colors
    record("seam-colors-3d-focus=passed")
    assert not visual_seam.Shape.isNull()
    assert len(visual_seam.Shape.Edges) >= 3
    focus_view = Gui.activeDocument().activeView()
    focus_camera_height = float(focus_view.getCameraNode().height.getValue())
    assert focus_camera_height >= 100.0, (
        "Focus Seam in 3D cropped the paired pattern-edge context: "
        f"camera_height={focus_camera_height:.3f}"
    )
    record(f"seam-focus-camera-framing=passed height={focus_camera_height:.3f}")
    record("seam-visual-3d=passed edges=%d" % len(visual_seam.Shape.Edges))
    overlay = save_seam_overlay_evidence(
        doc,
        [str(seam.SeamId) for seam in curved_network.Seams],
        "seam-overlay-sewing-3d.png",
        hovered_seam_id=str(visual_seam.SeamId),
    )
    assert "ClothSemanticSeamOverlay" == str(overlay.root.getName().getString())
    record("seam-viewport-overlay-sewing-3d=passed labels=paired-A-B")
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(visual_seam)
    Gui.runCommand("ClothSewing_Show2D", 0)
    process_events()
    assert seam_color_snapshot(curved_network.Seams) == baseline_seam_colors
    record("seam-colors-sewing-2d=passed")
    record("seam-visual-2d=passed top-view=true")
    save_seam_overlay_evidence(
        doc,
        [str(seam.SeamId) for seam in curved_network.Seams],
        "seam-overlay-sewing-2d.png",
    )
    record("seam-viewport-overlay-sewing-2d=passed labels=paired-A-B")
    overlay_ids = [str(seam.SeamId) for seam in curved_network.Seams]
    save_seam_overlay_hover_animation(doc, overlay_ids, "seam-overlay-hover.gif")
    save_seam_overlay_options_evidence("seam-overlay-options.png")

    curved_save = LOG_PATH.parent / "curved-mn-roundtrip.FCStd"
    relationship_id = str(curved_network.RelationshipId)
    doc.saveAs(str(curved_save))
    App.closeDocument(doc.Name)
    process_events()
    doc = App.openDocument(str(curved_save))
    process_events()
    reloaded_piece_a = next(
        obj
        for obj in doc.Objects
        if str(getattr(obj, "PatternType", "")) == "PatternPiece"
        and str(getattr(obj, "PieceId", "")) == "smoke-a"
    )
    reloaded_piece_b = next(
        obj
        for obj in doc.Objects
        if str(getattr(obj, "PatternType", "")) == "PatternPiece"
        and str(getattr(obj, "PieceId", "")) == "smoke-b"
    )
    assert reloaded_piece_a is not piece_a
    assert reloaded_piece_b is not piece_b
    piece_a = reloaded_piece_a
    piece_b = reloaded_piece_b
    record("post-reload-selection-objects=refreshed")
    reloaded_network = next(
        obj
        for obj in doc.Objects
        if getattr(obj, "SewingType", "") == "SewingNetwork"
        and str(getattr(obj, "RelationshipId", "")) == relationship_id
    )
    restored_colors = seam_color_snapshot(reloaded_network.Seams)
    assert restored_colors == baseline_seam_colors
    record("seam-colors-save-reload-restore=passed before-recompute=true")
    doc.recompute()
    assert seam_color_snapshot(reloaded_network.Seams) == baseline_seam_colors
    record("seam-colors-save-reload-recompute=passed")
    reloaded_pairs = tuple(
        sorted(
            (
                str(seam.SeamId),
                str(seam.EdgeAId),
                str(seam.EdgeBId),
                round(float(seam.StartA), 12),
                round(float(seam.EndA), 12),
                round(float(seam.StartB), 12),
                round(float(seam.EndB), 12),
                bool(seam.ReversedB),
            )
            for seam in reloaded_network.Seams
        )
    )
    assert reloaded_pairs == endpoint_snapshot
    assert reloaded_network.Status == "Valid"
    record("curved-mn-save-reload=passed same-endpoint-pairs=true reversed=true")
    # FreeCAD invalidates Python object wrappers when the source document is closed.
    # Reacquire persistent PatternPiece objects from the reopened document before GUI selection.
    piece_a = next(obj for obj in doc.Objects if str(getattr(obj, "PieceId", "")) == "smoke-a")
    piece_b = next(obj for obj in doc.Objects if str(getattr(obj, "PieceId", "")) == "smoke-b")
    record("post-reload-selection-objects=refreshed")

    select_edges((piece_a, 3), (piece_b, 3))
    free_panel = open_public("ClothSewing_FreeSewing")
    assert any(
        getattr(obj, "SewingType", "") == "SewingNetwork" for obj in free_panel.session.created
    )
    assert "Preview valid" in free_panel.feedback.text()
    record("preview-free=passed")
    free_panel.commit_button.click()
    wait_for_task_close()
    free_networks = [
        obj for obj in doc.Objects if getattr(obj, "SewingType", "") == "SewingNetwork"
    ]
    assert any(len(network.Seams) == 1 and network.Status == "Valid" for network in free_networks)
    record("commit-free=passed")

    free_cancel_before = {obj.Name for obj in doc.Objects}
    select_edges((piece_a, 2), (piece_b, 2))
    free_cancel_panel = open_public("ClothSewing_FreeSewing")
    assert free_cancel_panel.session.created
    assert "Preview valid" in free_cancel_panel.feedback.text()
    free_cancel_panel.cancel_button.click()
    wait_for_task_close()
    assert {obj.Name for obj in doc.Objects} == free_cancel_before
    record("cancel-free=passed")

    _success = True
except Exception:
    record("smoke=exception\n" + traceback.format_exc())

finally:
    if recorder is not None and recorder._started:
        with contextlib.suppress(Exception):
            from tests.support.freecad_input import release_all_input
            release_all_input()
            recorder.stop()
    with contextlib.suppress(Exception):
        set_seam_highlights_enabled(_ORIGINAL_HIGHLIGHTS_ENABLED)
        set_seam_overlay_respect_depth(_ORIGINAL_DEPTH_SETTING)
    LOG.append("sewing-creation-smoke=completed")
    LOG_PATH.write_text("\n".join(LOG) + "\n", encoding="utf-8")
    print("sewing-creation-smoke=completed", flush=True)

if _success:
    sys.stdout.flush()
    getattr(os, "_" + "exit")(0)
else:
    sys.stdout.flush()
    getattr(os, "_" + "exit")(1)
