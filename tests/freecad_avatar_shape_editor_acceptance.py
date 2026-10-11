"""FreeCAD GUI acceptance and animated evidence for avatar shape editing."""

from __future__ import annotations

import contextlib
import math
import os
import re
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import FreeCAD as App
import FreeCADGui as Gui

from tests.support.freecad_input import UiGifRecorder, focus_main_window


class _Event:
    """Small event adapter for driving the controller through the same callback path."""

    def __init__(self, position, state=None, button=None):
        self._position = (int(round(position[0])), int(round(position[1])))
        self._state = state
        self._button = button

    def getPosition(self):
        return self._position

    def getState(self):
        return self._state

    def getButton(self):
        return self._button


class _Callback:
    """Pivy callback adapter accepted by the controller's event entry points."""

    def __init__(self, event):
        self._event = event
        self.handled = False

    def getEvent(self):
        return self._event

    def setHandled(self):
        self.handled = True


def _events():
    """Flush FreeCAD paint and Qt signals before capturing the UI."""
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    app = QtWidgets.QApplication.instance()
    Gui.updateGui()
    if app is not None:
        app.processEvents()
    Gui.updateGui()
    if app is not None:
        app.processEvents()


def _mesh_points(avatar):
    """Return stable rounded geometry data for a before/after comparison."""
    return tuple(
        (round(float(point.x), 4), round(float(point.y), 4), round(float(point.z), 4))
        for point in avatar.Mesh.Points
    )


def _head_envelope(points, cutoff):
    """Return a stable geometric signature of the mannequin head region."""
    selected = tuple(sorted(point for point in points if point[2] >= cutoff))
    if len(selected) < 10:
        raise RuntimeError("too few mannequin vertices in the head envelope for a locality check")
    return selected


def _camera_signature(view):
    """Capture camera framing only, excluding clipping-plane updates."""
    camera_text = str(view.getCamera())
    signature = {}
    for name in ("position", "orientation", "focalDistance", "height", "heightAngle"):
        match = re.search(
            rf"(?m)^\s*{re.escape(name)}\s+([^\r\n]+)",
            camera_text,
        )
        if match:
            signature[name] = tuple(float(value) for value in match.group(1).split())
    required = {"position", "orientation", "focalDistance"}
    if not required.issubset(signature) or not ({"height", "heightAngle"} & signature.keys()):
        raise RuntimeError("could not inspect the viewport camera framing")
    return signature


def _assert_camera_stable(before, after):
    """Fail if an in-place mesh rebuild changes the active camera framing."""
    if set(before) != set(after):
        raise RuntimeError("camera framing fields changed during avatar rebuild")
    for name, old_values in before.items():
        new_values = after[name]
        if len(old_values) != len(new_values) or any(
            not math.isclose(old, new, rel_tol=0.0, abs_tol=1e-4)
            for old, new in zip(old_values, new_values, strict=True)
        ):
            raise RuntimeError(
                f"avatar rebuild changed camera framing: {name} {old_values} -> {new_values}"
            )


def _shape_change_summary(before, after, height_mm):
    """Measure changed torso geometry independently of native point order/count."""
    before_keys = {tuple(round(value, 1) for value in point) for point in before}

    def key(point):
        return tuple(round(value, 1) for value in point)

    changed_positions = tuple(point for point in after if key(point) not in before_keys)
    torso_changed_vertices = sum(
        1
        for point in changed_positions
        if 0.50 * height_mm <= point[2] <= 0.80 * height_mm
    )
    before_front = tuple(
        point[1]
        for point in before
        if 0.64 * height_mm <= point[2] <= 0.73 * height_mm
        and point[1] > 0.0
        and abs(point[0]) <= 160.0
    )
    after_front = tuple(
        point[1]
        for point in after
        if 0.64 * height_mm <= point[2] <= 0.73 * height_mm
        and point[1] > 0.0
        and abs(point[0]) <= 160.0
    )
    if not before_front or not after_front:
        raise RuntimeError("no front-facing upper-torso vertices available for shape review")
    return {
        "changed_vertices": len(changed_positions),
        "torso_changed_vertices": torso_changed_vertices,
        "max_bust_projection_delta_mm": max(after_front) - max(before_front),
    }


def _capture_screen(path):
    """Capture and validate the visible 1280 x 720 FreeCAD window."""
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets

    app = QtWidgets.QApplication.instance()
    screen = None if app is None else app.primaryScreen()
    window = Gui.getMainWindow()
    if app is None or screen is None or window is None:
        raise RuntimeError("FreeCAD main window/screen is unavailable for shape-editor capture")
    geometry = screen.availableGeometry()
    if geometry.width() < 1280 or geometry.height() < 720:
        raise RuntimeError(
            "Avatar shape capture requires a 1280x720-capable screen, got %dx%d"
            % (geometry.width(), geometry.height())
        )
    window.resize(1280, 720)
    window.show()
    if hasattr(window, "raise_"):
        window.raise_()
    if hasattr(window, "activateWindow"):
        window.activateWindow()
    _events()
    pixmap = screen.grabWindow(int(window.winId()))
    if pixmap.isNull():
        raise RuntimeError("FreeCAD main-window screenshot is null")
    if (int(pixmap.width()), int(pixmap.height())) != (1280, 720):
        raise RuntimeError(
            "Avatar shape screenshot dimensions are %dx%d, expected 1280x720"
            % (int(pixmap.width()), int(pixmap.height()))
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    if not pixmap.save(str(path)):
        raise RuntimeError("could not save avatar shape-editor screenshot")
    from freecad_cloth.common.VisualCaptureValidation import validate_png_capture

    return validate_png_capture(
        path,
        expected_width=1280,
        expected_height=720,
        min_nonwhite_pixels=500,
        min_distinct_rgb=16,
        min_opaque_pixels=500,
    )


def _drag_dimension_handle(controller, coin, key, pixels=6.0):
    """Stage a dimension by travelling along the projected viewport handle axis."""
    item = next((entry for entry in controller._specs() if entry["key"] == key), None)
    if item is None:
        raise RuntimeError("missing viewport dimension handle: " + str(key))
    initial_value = float(controller.panel._boxes[key].value())
    start = controller._screen_position(item["point"])
    axis = controller._screen_axis(item)
    axis_length = math.hypot(axis[0], axis[1])
    if axis_length <= 1e-8:
        raise RuntimeError("dimension handle has no visible projected drag axis: " + str(key))
    size = controller.view.getSize()
    start_event_position = (start[0], float(size[1]) - start[1])
    down = _Callback(
        _Event(
            start_event_position,
            coin.SoMouseButtonEvent.DOWN,
            coin.SoMouseButtonEvent.BUTTON1,
        )
    )
    controller._mouse_event(down)
    if controller._drag_key != key:
        raise RuntimeError("viewport pick did not start dragging " + str(key))

    unit = (axis[0] / axis_length, axis[1] / axis_length)
    end = (start[0] + unit[0] * float(pixels), start[1] + unit[1] * float(pixels))
    motion_event_position = (end[0], float(size[1]) - end[1])
    controller._location_event(_Callback(_Event(motion_event_position)))
    staged_value = float(controller.panel._boxes[key].value())
    up = _Callback(
        _Event(
            motion_event_position,
            coin.SoMouseButtonEvent.UP,
            coin.SoMouseButtonEvent.BUTTON1,
        )
    )
    controller._mouse_event(up)
    _events()
    if controller._drag_key is not None:
        raise RuntimeError("viewport dimension drag did not terminate cleanly")
    if abs(staged_value - initial_value) < 1.0:
        raise RuntimeError(
            "viewport dimension drag did not stage a measurable change: "
            + repr((key, initial_value, staged_value))
        )
    return initial_value, staged_value


def run():
    """Exercise body-shape controls, viewport dimension staging, and saved rebuilds."""
    Path("artifacts/ui-gifs").mkdir(parents=True, exist_ok=True)
    from freecad_cloth.avatar.AvatarCommands import create_avatar
    from freecad_cloth.avatar.AvatarGui import AvatarTaskPanel

    doc = App.newDocument("AvatarShapeEditorAcceptance")
    try:
        avatar = create_avatar(attach_collision=False, doc=doc, object_name="ShapeEditorMannequin")
        avatar.Label = "Mannequin / Sewing Fit Example"
        doc.recompute()
        original_mesh = _mesh_points(avatar)
        original_facets = len(avatar.Mesh.Facets)
        original_names = {str(obj.Name) for obj in doc.Objects}

        panel = AvatarTaskPanel(avatar)
        Gui.Control.showDialog(panel)
        focus_main_window(Gui, size=(1280, 720))
        active = Gui.activeDocument()
        if active is None:
            raise RuntimeError("there is no active FreeCAD document for shape editor acceptance")
        view = active.activeView()
        view.viewIsometric()
        view.fitAll()
        view.zoomIn()
        view.zoomIn()
        _events()

        # The transient overlay must not create FreeCAD document objects.
        panel._toggle_dimension_gizmo(True)
        controller = panel._dimension_controller
        if controller is None or controller.view is None or controller.overlay is None:
            raise RuntimeError(
                "3D Dimensions did not activate; viewport shape editing must remain visible"
            )
        if {str(obj.Name) for obj in doc.Objects} != original_names:
            raise RuntimeError("viewport dimension overlay created persistent document objects")

        # Dimension rings are useful for the separate measurement-drag clip,
        # but obscure the torso in a body-shape demonstration.
        panel.dimension_gizmo_toggle.setChecked(False)
        _events()
        if controller.overlay is not None:
            raise RuntimeError("dimension overlay remained visible for shape-edit recording")

        shape_recorder = UiGifRecorder(
            "artifacts/ui-gifs/avatar-shape-edit.gif",
            gui=Gui,
            window=Gui.getMainWindow(),
            fps=10,
            scale=0.5,
            max_frames=100,
            show_cursor=False,
        )
        shape_recorder.start()
        try:
            shape_recorder.hold(500)
            panel.gender_slider.setValue(20)
            panel.breast_slider.setValue(65)
            _events()
            shape_recorder.hold(650)
            staged = panel._staged_parameters()
            if abs(staged.gender - 0.20) > 1e-6 or abs(staged.breast_size - 0.65) > 1e-6:
                raise RuntimeError("body shape sliders did not stage their expected values")
            camera_before_rebuild = _camera_signature(view)
            if not panel._apply():
                raise RuntimeError(
                    "Apply & Rebuild rejected staged body-shape values: " + str(panel.status.text())
                )
            _events()
            _assert_camera_stable(camera_before_rebuild, _camera_signature(view))
            shape_recorder.hold(750)
            if abs(float(avatar.GenderBlend) - 0.20) > 1e-6:
                raise RuntimeError("gender blend did not persist to the FreeCAD avatar object")
            if abs(float(avatar.BreastSize) - 0.65) > 1e-6:
                raise RuntimeError("breast fullness did not persist to the FreeCAD avatar object")
            updated_mesh = _mesh_points(avatar)
            updated_facets = len(avatar.Mesh.Facets)
            if updated_facets != original_facets:
                raise RuntimeError(
                    "avatar shape rebuild changed facet count: {} -> {}".format(
                        original_facets, updated_facets
                    )
                )
            shape_delta = _shape_change_summary(original_mesh, updated_mesh, float(avatar.Height))
            if shape_delta["changed_vertices"] == 0:
                raise RuntimeError("body-shape Apply & Rebuild did not change mannequin geometry")
            if shape_delta["torso_changed_vertices"] == 0:
                raise RuntimeError("body-shape rebuild did not change the torso region")
            if shape_delta["max_bust_projection_delta_mm"] < 1.0:
                raise RuntimeError(
                    "breast fullness did not visibly move the front torso surface: "
                    + repr(shape_delta)
                )
        finally:
            if shape_recorder._started:
                shape_recorder.stop()

        # Re-enable viewport handles for the distinct hip-measurement clip.
        panel.dimension_gizmo_toggle.setChecked(True)
        _events()
        controller = panel._dimension_controller
        if controller is None or controller.view is None or controller.overlay is None:
            raise RuntimeError("3D dimensions did not reactivate for hip-drag recording")

        # Record a distinct viewport-first circumference edit: drag the hip
        # handle, watch the ring/readout update, then commit via Apply & Rebuild.
        from pivy import coin

        dimension_recorder = UiGifRecorder(
            "artifacts/ui-gifs/avatar-dimension-drag.gif",
            gui=Gui,
            window=Gui.getMainWindow(),
            fps=10,
            scale=0.5,
            max_frames=100,
            show_cursor=False,
        )
        dimension_recorder.start()
        before_hip_mesh = _mesh_points(avatar)
        head_cutoff = max(point[2] for point in before_hip_mesh) * 0.88
        head_before_hip = _head_envelope(before_hip_mesh, head_cutoff)
        try:
            dimension_recorder.hold(450)
            hip_before, hip_staged = _drag_dimension_handle(
                controller,
                coin,
                "hip",
                pixels=5.0,
            )
            dimension_recorder.hold(700)
            if abs(float(panel._boxes["hip"].value()) - hip_staged) > 1e-6:
                raise RuntimeError("viewport hip handle and numeric value diverged")
            camera_before_hip_rebuild = _camera_signature(view)
            if not panel._apply():
                raise RuntimeError("Apply & Rebuild rejected the staged hip measurement")
            _events()
            _assert_camera_stable(camera_before_hip_rebuild, _camera_signature(view))
            dimension_recorder.hold(700)
            hip_after = float(avatar.Hip)
            if abs(hip_after - hip_staged) > 1e-6:
                raise RuntimeError("viewport hip drag was not persisted on rebuild")
            if abs(hip_after - hip_before) < 1.0:
                raise RuntimeError("viewport hip drag produced no persistent dimensional change")
            if _head_envelope(_mesh_points(avatar), head_cutoff) != head_before_hip:
                raise RuntimeError(
                    "hip circumference edit changed the head geometry instead of staying local"
                )
        finally:
            if dimension_recorder._started:
                dimension_recorder.stop()

        _events()
        metrics = _capture_screen(Path("artifacts/avatar-shape-editor.png"))
        if abs(float(avatar.GenderBlend) - 0.20) > 1e-6:
            raise RuntimeError("gender blend changed unexpectedly during dimension editing")
        if abs(float(avatar.BreastSize) - 0.65) > 1e-6:
            raise RuntimeError("breast fullness changed unexpectedly during dimension editing")
        if _mesh_points(avatar) == original_mesh:
            raise RuntimeError("committed avatar geometry reverted to its original shape")

        Path("artifacts/avatar-shape-editor.log").write_text(
            "avatar-shape-editor=passed "
            "gender=0.20 breast_size=0.65 "
            "shape_changed_vertices={shape_changed} torso_changed_vertices={torso_changed} "
            "max_bust_projection_delta_mm={bust_delta:.2f} "
            "hip_before={hip_before:.2f} hip_after={hip_after:.2f} "
            "document_objects_overlay=transient "
            "screenshot_opaque_pixels={opaque} screenshot_distinct_rgb={distinct}\n".format(
                shape_changed=shape_delta["changed_vertices"],
                torso_changed=shape_delta["torso_changed_vertices"],
                bust_delta=shape_delta["max_bust_projection_delta_mm"],
                hip_before=hip_before,
                hip_after=hip_after,
                opaque=metrics["opaque_pixels"],
                distinct=metrics["distinct_rgb"],
            ),
            encoding="utf-8",
        )
        print(
            "avatar-shape-editor=passed gender=0.20 breast_size=0.65 "
            "shape_changed_vertices={} torso_changed_vertices={} "
            "max_bust_projection_delta_mm={:.2f} "
            "hip_before={:.2f} hip_after={:.2f}".format(
                shape_delta["changed_vertices"],
                shape_delta["torso_changed_vertices"],
                shape_delta["max_bust_projection_delta_mm"],
                hip_before,
                hip_after,
            ),
            flush=True,
        )
        panel.reject()
        doc.recompute()
    finally:
        if Gui.Control.activeDialog():
            with contextlib.suppress(AttributeError, RuntimeError):
                Gui.Control.closeDialog()
        if App.ActiveDocument is not None and App.ActiveDocument.Name == doc.Name:
            App.closeDocument(doc.Name)


try:
    run()
except BaseException as exc:
    Path("artifacts").mkdir(parents=True, exist_ok=True)
    Path("artifacts/avatar-shape-editor.log").write_text(
        "avatar-shape-editor=failed\n" + repr(exc) + "\n" + traceback.format_exc(),
        encoding="utf-8",
    )
    print("avatar-shape-editor=failed", exc, flush=True)
    App.Console.PrintError("Avatar shape editor acceptance failed: %s\n" % exc)
    os._exit(1)
os._exit(0)
