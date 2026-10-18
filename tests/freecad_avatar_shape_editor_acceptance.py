# Copyright (C) 2026 FreeCAD Cloth contributors
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

# FreeCAD's fitted-mesh/FK rebuild shows sub-micrometre residual movement at the head;
# keep native vertex correspondence and point counts exact while filtering only that numerical noise.
HEAD_LOCALITY_TOLERANCE_MM = 0.001


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


def _mesh_points_unrounded(avatar) -> tuple[tuple[float, float, float], ...]:
    """Return full-precision vertices in native index order for locality checks."""
    return tuple((float(point.x), float(point.y), float(point.z)) for point in avatar.Mesh.Points)


def _head_envelope(points, cutoff):
    """Return indexed head vertices so a rebuild can be checked by correspondence."""
    selected = tuple((index, point) for index, point in enumerate(points) if point[2] >= cutoff)
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


def _shape_change_summary(
    before: tuple[tuple[float, float, float], ...],
    after: tuple[tuple[float, float, float], ...],
    height_mm: float,
    breast_reference: tuple[tuple[float, float, float], ...] | None = None,
) -> dict[str, float | int]:
    """Measure changed torso geometry independently of native point order/count."""
    before_keys = {tuple(round(value, 1) for value in point) for point in before}

    def key(point: tuple[float, float, float]) -> tuple[float, float, float]:
        return tuple(round(value, 1) for value in point)

    changed_positions = tuple(point for point in after if key(point) not in before_keys)
    torso_changed_vertices = sum(
        1 for point in changed_positions if 0.50 * height_mm <= point[2] <= 0.80 * height_mm
    )
    bust_baseline = before if breast_reference is None else breast_reference
    if len(bust_baseline) != len(after):
        raise RuntimeError("bust projection comparison requires matched generated mesh topology")

    # clad-body uses Z-up and +Y-anterior. Use baseline vertex indices as the
    # lobe correspondence, then measure each corresponding vertex's forward
    # displacement. Taking max(Y) independently on two different point clouds
    # can select an unrelated extremum and hide a real local shape change.
    def front_lobe_indices(
        points: tuple[tuple[float, float, float], ...], side: float
    ) -> tuple[int, ...]:
        return tuple(
            index
            for index, point in enumerate(points)
            if 0.64 * height_mm <= point[2] <= 0.73 * height_mm
            and point[1] > 0.0
            and 25.0 <= side * point[0] <= 155.0
        )

    # Anny/clad-body centres each fitted mesh on its own XY bounds. Cupsize can
    # therefore translate the whole torso when the breast envelope changes; compare
    # lobe displacement relative to the lower torso to isolate actual prominence.
    torso_reference_indices = tuple(
        index
        for index, point in enumerate(bust_baseline)
        if 0.48 * height_mm <= point[2] <= 0.61 * height_mm
        and point[1] > 0.0
        and 20.0 <= abs(point[0]) <= 130.0
    )
    if not torso_reference_indices:
        raise RuntimeError("no lower-torso vertices available to normalize bust projection")
    torso_y_shift = sorted(
        after[index][1] - bust_baseline[index][1] for index in torso_reference_indices
    )[len(torso_reference_indices) // 2]

    side_deltas: dict[str, float] = {}
    side_absolute_deltas: dict[str, float] = {}
    side_max_abs_axis_delta: dict[str, tuple[float, float, float]] = {}
    side_max_vertex_delta: dict[str, float] = {}
    side_lobe_vertex_counts: dict[str, int] = {}
    for side, name in ((-1.0, "left"), (1.0, "right")):
        lobe_indices = front_lobe_indices(bust_baseline, side)
        if not lobe_indices:
            raise RuntimeError(f"no front-facing {name} breast vertices available for shape review")
        deltas = tuple(
            tuple(after[index][axis] - bust_baseline[index][axis] for axis in range(3))
            for index in lobe_indices
        )
        side_absolute_deltas[name] = max(delta[1] for delta in deltas)
        side_deltas[name] = side_absolute_deltas[name] - torso_y_shift
        side_max_abs_axis_delta[name] = tuple(
            max(abs(delta[axis]) for delta in deltas) for axis in range(3)
        )
        side_max_vertex_delta[name] = max(
            math.sqrt(sum(component * component for component in delta)) for delta in deltas
        )
        side_lobe_vertex_counts[name] = len(lobe_indices)
    return {
        "changed_vertices": len(changed_positions),
        "torso_changed_vertices": torso_changed_vertices,
        "torso_reference_y_shift_mm": torso_y_shift,
        "left_bust_absolute_y_delta_mm": side_absolute_deltas["left"],
        "right_bust_absolute_y_delta_mm": side_absolute_deltas["right"],
        "left_bust_projection_delta_mm": side_deltas["left"],
        "right_bust_projection_delta_mm": side_deltas["right"],
        "min_side_bust_projection_delta_mm": min(side_deltas.values()),
        "max_bust_projection_delta_mm": max(side_deltas.values()),
        "left_lobe_max_abs_dx_mm": side_max_abs_axis_delta["left"][0],
        "left_lobe_max_abs_dy_mm": side_max_abs_axis_delta["left"][1],
        "left_lobe_max_abs_dz_mm": side_max_abs_axis_delta["left"][2],
        "right_lobe_max_abs_dx_mm": side_max_abs_axis_delta["right"][0],
        "right_lobe_max_abs_dy_mm": side_max_abs_axis_delta["right"][1],
        "right_lobe_max_abs_dz_mm": side_max_abs_axis_delta["right"][2],
        "left_lobe_max_vertex_delta_mm": side_max_vertex_delta["left"],
        "right_lobe_max_vertex_delta_mm": side_max_vertex_delta["right"],
        "left_lobe_vertex_count": side_lobe_vertex_counts["left"],
        "right_lobe_vertex_count": side_lobe_vertex_counts["right"],
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
    os.environ["CLOTH_ANNY_SHAPE_TRACE"] = "1"
    Path("artifacts/ui-gifs").mkdir(parents=True, exist_ok=True)
    from freecad_cloth.avatar.AvatarCommands import _parameters, create_avatar
    from freecad_cloth.avatar.AvatarGui import AvatarTaskPanel
    from freecad_cloth.avatar.AvatarModel import generate_mesh

    doc = App.newDocument("AvatarShapeEditorAcceptance")
    try:
        avatar = create_avatar(attach_collision=False, doc=doc, object_name="ShapeEditorMannequin")
        avatar.Label = "Mannequin / Sewing Fit Example"
        doc.recompute()
        original_native_mesh = _mesh_points(avatar)
        original_mesh, original_triangles, _original_landmarks = generate_mesh(_parameters(avatar))
        original_facets = len(avatar.Mesh.Facets)
        original_names = {str(obj.Name) for obj in doc.Objects}

        panel = AvatarTaskPanel(avatar)
        Gui.Control.showDialog(panel)

        # The advanced editor must discover the installed Anny controls, stage
        # both parameter families, support cross-tab search, and reset cleanly.
        panel.advanced_toggle.setChecked(True)
        _events()
        if not panel._advanced_controls_built:
            raise RuntimeError("advanced Anny parameters did not load on demand")
        age_control = next(
            (
                item
                for item in panel._advanced_rows
                if item["kind"] == "phenotype" and item["name"] == "age"
            ),
            None,
        )
        waist_morph = next(
            (
                item
                for item in panel._advanced_rows
                if item["kind"] == "morph" and "measure-waist-circ" in item["name"]
            ),
            None,
        )
        if age_control is None or waist_morph is None:
            raise RuntimeError("advanced Anny phenotype/body-morph parameters are incomplete")
        age_control["box"].setValue(min(1.0, age_control["default"] + 0.05))
        waist_morph["box"].setValue(0.1)
        advanced_staged = panel._staged_parameters()
        if not advanced_staged.phenotype_overrides or not advanced_staged.local_change_overrides:
            raise RuntimeError("advanced Anny parameter edits were not staged")
        panel.advanced_search.setText("measure-waist-circ")
        _events()
        if not waist_morph["row"].isVisible() or panel.advanced_tabs.currentIndex() != 1:
            raise RuntimeError("advanced parameter search did not reveal the matching body morph")
        panel.advanced_search.clear()
        panel.reset_advanced_button.click()
        if panel._advanced_phenotype_overrides or panel._advanced_local_change_overrides:
            raise RuntimeError("Reset advanced did not clear all advanced overrides")
        panel.advanced_toggle.setChecked(False)

        # Mass is an optional native-unit clad-body target, separate from mm fields.
        panel.mass_target_enabled.setChecked(True)
        panel.mass_target.setValue(68.5)
        if panel._staged_parameters().mass_target_kg != 68.5:
            raise RuntimeError("body-mass target did not stage in kilograms")
        panel.mass_target_enabled.setChecked(False)
        if panel._staged_parameters().mass_target_kg is not None:
            raise RuntimeError("disabling the body-mass target did not remove the constraint")
        _events()

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
            updated_native_mesh = _mesh_points(avatar)
            updated_facets = len(avatar.Mesh.Facets)
            if updated_facets != original_facets:
                raise RuntimeError(
                    f"avatar shape rebuild changed facet count: {original_facets} -> {updated_facets}"
                )
            from dataclasses import replace as replace_parameters

            committed_parameters = panel._staged_parameters()
            updated_mesh, updated_triangles, _updated_landmarks = generate_mesh(
                committed_parameters
            )
            zero_fullness_vertices, zero_fullness_triangles, _landmarks = generate_mesh(
                replace_parameters(committed_parameters, breast_size=0.0)
            )
            if (
                len(original_mesh) != len(updated_mesh)
                or updated_triangles != zero_fullness_triangles
                or updated_triangles != original_triangles
            ):
                raise RuntimeError(
                    "cupsize acceptance requires stable generated mesh vertex/triangle correspondence"
                )
            native_before_keys = {
                tuple(round(value, 1) for value in point) for point in original_native_mesh
            }
            native_changed_vertices = sum(
                tuple(round(value, 1) for value in point) not in native_before_keys
                for point in updated_native_mesh
            )
            if native_changed_vertices == 0:
                raise RuntimeError("body-shape rebuild did not change native FreeCAD mesh vertices")
            shape_delta = _shape_change_summary(
                original_mesh,
                updated_mesh,
                float(avatar.Height),
                breast_reference=zero_fullness_vertices,
            )
            if shape_delta["changed_vertices"] == 0:
                raise RuntimeError("body-shape Apply & Rebuild did not change mannequin geometry")
            if shape_delta["torso_changed_vertices"] == 0:
                raise RuntimeError("body-shape rebuild did not change the torso region")
            if shape_delta["min_side_bust_projection_delta_mm"] < 1.0:
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
        before_hip_mesh = _mesh_points_unrounded(avatar)
        before_hip_measurements = {name: float(box.value()) for name, box in panel._boxes.items()}
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
            after_hip_mesh = _mesh_points_unrounded(avatar)
            head_after_hip = _head_envelope(after_hip_mesh, head_cutoff)
            before_by_index = dict(head_before_hip)
            after_by_index = dict(head_after_hip)
            shared_indices = before_by_index.keys() & after_by_index.keys()
            displacement_records = tuple(
                (
                    math.dist(before_by_index[index], after_by_index[index]),
                    index,
                    before_by_index[index],
                    after_by_index[index],
                )
                for index in shared_indices
            )
            largest_displacement = max(
                displacement_records,
                key=lambda record: record[0],
                default=(float("inf"), -1, (), ()),
            )
            head_indices_stable = before_by_index.keys() == after_by_index.keys()
            if (
                not head_indices_stable
                or largest_displacement[0] > HEAD_LOCALITY_TOLERANCE_MM
                or len(before_hip_mesh) != len(after_hip_mesh)
            ):
                before_head_set = set(before_by_index)
                after_head_set = set(after_by_index)
                after_hip_measurements = {
                    name: float(box.value()) for name, box in panel._boxes.items()
                }
                changed_measurements = {
                    name: (before_hip_measurements[name], value)
                    for name, value in after_hip_measurements.items()
                    if abs(value - before_hip_measurements[name]) > 1e-6
                }

                def _axis_bounds(points, axis):
                    values = tuple(point[axis] for point in points)
                    return min(values), max(values)

                before_head_points = tuple(point for _, point in head_before_hip)
                after_head_points = tuple(point for _, point in head_after_hip)
                before_bounds = tuple(_axis_bounds(before_head_points, axis) for axis in range(3))
                after_bounds = tuple(_axis_bounds(after_head_points, axis) for axis in range(3))
                largest_displacements = tuple(
                    (
                        index,
                        round(displacement, 9),
                        before_point,
                        after_point,
                    )
                    for displacement, index, before_point, after_point in sorted(
                        displacement_records,
                        key=lambda record: record[0],
                        reverse=True,
                    )[:3]
                )
                locality_diagnostic = {
                    "cutoff_mm": head_cutoff,
                    "tolerance_mm": HEAD_LOCALITY_TOLERANCE_MM,
                    "max_vertex_displacement_mm": largest_displacement[0],
                    "max_displacement_vertex_index": largest_displacement[1],
                    "before_head_count": len(head_before_hip),
                    "after_head_count": len(head_after_hip),
                    "before_bounds_mm": before_bounds,
                    "after_bounds_mm": after_bounds,
                    "removed_vertex_indices": sorted(before_head_set - after_head_set)[:3],
                    "added_vertex_indices": sorted(after_head_set - before_head_set)[:3],
                    "largest_vertex_displacements": largest_displacements,
                    "changed_measurements_mm": tuple(changed_measurements.items()),
                    "mesh_point_counts": (len(before_hip_mesh), len(after_hip_mesh)),
                }
                diagnostic_path = Path("artifacts/avatar-head-locality-diagnostic.txt")
                diagnostic_path.parent.mkdir(parents=True, exist_ok=True)
                diagnostic_path.write_text(repr(locality_diagnostic) + "\n", encoding="utf-8")
                print("avatar-head-locality-diagnostic " + repr(locality_diagnostic), flush=True)
                raise RuntimeError(
                    "hip circumference edit changed the head geometry instead of staying local: "
                    + repr(locality_diagnostic)
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
            "left_bust_delta_mm={left_bust:.2f} right_bust_delta_mm={right_bust:.2f} "
            "hip_before={hip_before:.2f} hip_after={hip_after:.2f} "
            "document_objects_overlay=transient "
            "screenshot_opaque_pixels={opaque} screenshot_distinct_rgb={distinct}\n".format(
                shape_changed=shape_delta["changed_vertices"],
                torso_changed=shape_delta["torso_changed_vertices"],
                left_bust=shape_delta["left_bust_projection_delta_mm"],
                right_bust=shape_delta["right_bust_projection_delta_mm"],
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
            "left_bust_delta_mm={:.2f} right_bust_delta_mm={:.2f} "
            "hip_before={:.2f} hip_after={:.2f}".format(
                shape_delta["changed_vertices"],
                shape_delta["torso_changed_vertices"],
                shape_delta["left_bust_projection_delta_mm"],
                shape_delta["right_bust_projection_delta_mm"],
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
