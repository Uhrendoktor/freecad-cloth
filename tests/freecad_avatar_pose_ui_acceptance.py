"""Real FreeCAD/Xvfb acceptance for the focused mannequin Pose Mode UI."""

import faulthandler
import os
from collections import defaultdict
from itertools import product
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import FreeCAD as App
import FreeCADGui as Gui

from tests.support.freecad_input import (
    UiGifRecorder,
    click_widget,
    type_text,
    wait_until,
)



def _runtime_diagnostics():
    import importlib.metadata
    import re

    info = {
        "freecad_version": getattr(App, "Version", lambda: "unknown")(),
        "freecad_coin_version": "unavailable",
        "freecad_swig_runtime": "unavailable",
        "freecadgui_module": "unavailable",
        "pivy_version": "unavailable",
        "pivy_module": "unavailable",
        "coin_version": "unavailable",
        "coin_module": "unavailable",
        "pivy_swig_runtime": "unavailable",
    }

    def swig_runtime_strings(path):
        try:
            data = Path(path).read_bytes()
            return sorted(
                {
                    match.decode("ascii")
                    for match in re.findall(rb"swig_runtime_data([0-9]+)", data)
                }
            )
        except (OSError, TypeError, ValueError):
            return []

    candidates = []
    for root_name in ("/opt/conda/envs/freecad", "/usr/local", "/usr/lib"):
        root = Path(root_name)
        if not root.exists():
            continue
        candidates.extend(
            sorted(
                path
                for path in root.rglob("*FreeCADGui*.so*")
                if path.is_file()
            )
        )
    info["freecadgui_candidates"] = [str(path) for path in candidates[:20]]

    try:
        import importlib.util

        try:
            gui_spec = importlib.util.find_spec("FreeCADGui")
        except (ImportError, ValueError):
            gui_spec = None
        gui_origin = getattr(gui_spec, "origin", None) if gui_spec is not None else None
        info["freecadgui_module"] = str(gui_origin or "unknown")
        if gui_origin:
            runtimes = swig_runtime_strings(gui_origin)
            if runtimes:
                info["freecad_swig_runtime"] = ",".join(runtimes)
        if info["freecad_swig_runtime"] == "unavailable":
            for candidate in candidates:
                runtimes = swig_runtime_strings(candidate)
                if runtimes:
                    info["freecadgui_module"] = str(candidate)
                    info["freecad_swig_runtime"] = ",".join(runtimes)
                    break
    except Exception as exc:
        info["freecad_runtime_error"] = repr(exc)

    try:
        info["freecad_coin_version"] = str(Gui.getSoDBVersion())
    except Exception as exc:
        info["freecad_coin_version"] = "error:" + repr(exc)

    try:
        import pivy

        info["pivy_module"] = str(getattr(pivy, "__file__", "unknown"))
        try:
            info["pivy_version"] = importlib.metadata.version("pivy")
        except importlib.metadata.PackageNotFoundError:
            info["pivy_version"] = "metadata-unavailable"

        from pivy import coin

        info["coin_module"] = str(getattr(coin, "__file__", "unknown"))
        info["coin_version"] = str(coin.SoDB.getVersion())
        coin_module = Path(info["coin_module"])
        candidates = [coin_module.with_name("_coin.so"), coin_module.with_name("_coin.pyd")]
        candidates.extend(sorted(coin_module.parent.glob("_coin*.so")))
        candidates.extend(sorted(coin_module.parent.glob("_coin*.pyd")))
        for candidate in candidates:
            runtimes = swig_runtime_strings(candidate)
            if runtimes:
                info["pivy_swig_runtime"] = ",".join(runtimes)
                info["pivy_binary"] = str(candidate)
                break
    except Exception as exc:
        info["runtime_error"] = repr(exc)
    return info

def _events():
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


def _capture_pose_screen(path, panel, view):
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets

    app = QtWidgets.QApplication.instance()
    screen = None if app is None else app.primaryScreen()
    window = Gui.getMainWindow()
    if app is None or screen is None or window is None:
        raise RuntimeError("FreeCAD main window/screen is unavailable for Pose Mode screenshot")

    geometry = screen.availableGeometry()
    if geometry.width() < 1280 or geometry.height() < 720:
        raise RuntimeError(
            "Pose Mode screenshot requires a 1280x720-capable screen, got %dx%d"
            % (geometry.width(), geometry.height())
        )

    window.resize(1280, 720)
    window.show()
    if hasattr(window, "raise_"):
        window.raise_()
    if hasattr(window, "activateWindow"):
        window.activateWindow()
    _events()

    view.viewIsometric()
    view.fitAll()
    panel.controller.select_joint("upperarm01.L")
    _events()
    view.redraw()
    time.sleep(0.10)
    _events()

    pixmap = screen.grabWindow(int(window.winId()))
    if pixmap.isNull():
        raise RuntimeError("FreeCAD main-window screenshot is null")
    width, height = int(pixmap.width()), int(pixmap.height())
    if (width, height) != (1280, 720):
        raise RuntimeError(
            "Pose Mode screenshot dimensions are %dx%d, expected 1280x720" % (width, height)
        )
    if not pixmap.save(str(path)):
        raise RuntimeError("failed to save Pose Mode UI screenshot")

    from freecad_cloth.common.VisualCaptureValidation import validate_png_capture

    return validate_png_capture(
        path,
        expected_width=1280,
        expected_height=720,
        min_nonwhite_pixels=500,
        min_distinct_rgb=16,
        min_opaque_pixels=500,
    )


def _bounds(mesh):
    box = mesh.BoundBox
    return (
        float(box.XMin),
        float(box.XMax),
        float(box.YMin),
        float(box.YMax),
        float(box.ZMin),
        float(box.ZMax),
    )


def _point_bounds(points):
    values = tuple(
        (float(point[0]), float(point[1]), float(point[2]))
        for point in points
    )
    if not values:
        return None
    return tuple(
        (
            min(point[axis] for point in values),
            max(point[axis] for point in values),
        )
        for axis in range(3)
    )


def _point_records(points, precision=3):
    """Return a stable, order-independent point multiset at native mesh precision."""
    records = []
    for point in points:
        values = tuple(float(value) for value in point)
        key = tuple(round(value, precision) for value in values)
        records.append((key, values))
    return sorted(records)


def _match_native_points(expected_points, actual_points, tolerance=0.002):
    """Match points one-to-one within native mesh precision, independent of ordering."""
    buckets = defaultdict(list)
    actual_values = tuple(
        tuple(float(value) for value in point) for point in actual_points
    )
    for index, point in enumerate(actual_values):
        key = tuple(int(value // tolerance) for value in point)
        buckets[key].append((index, point))

    matched = set()
    max_error = 0.0
    for expected_index, raw_expected in enumerate(expected_points):
        expected = tuple(float(value) for value in raw_expected)
        key = tuple(int(value // tolerance) for value in expected)
        best_index = None
        best_point = None
        best_error = float("inf")
        for delta in product((-1, 0, 1), repeat=3):
            neighbor_key = tuple(key[axis] + delta[axis] for axis in range(3))
            for actual_index, actual in buckets.get(neighbor_key, ()):
                if actual_index in matched:
                    continue
                error = sum(
                    (actual[axis] - expected[axis]) ** 2 for axis in range(3)
                ) ** 0.5
                if error < best_error:
                    best_index, best_point, best_error = (
                        actual_index,
                        actual,
                        error,
                    )
        if best_index is None or best_error > tolerance:
            return max_error, (
                expected_index,
                expected,
                best_point,
                best_error,
            )
        matched.add(best_index)
        max_error = max(max_error, best_error)

    if len(matched) != len(actual_values):
        return max_error, (
            len(expected_points),
            None,
            None,
            float("inf"),
        )
    return max_error, None


def run():
    progress_path = Path("artifacts/avatar-pose-ui-progress.log")
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    trace = progress_path.open("w", encoding="utf-8", buffering=1)
    faulthandler.enable(file=trace, all_threads=True)
    try:
        faulthandler.dump_traceback_later(30.0, repeat=True, file=trace)
    except (AttributeError, RuntimeError, OSError):
        pass

    def progress(message):
        trace.write(str(message) + "\n")
        trace.flush()

    progress("start")
    from freecad_cloth.avatar.AvatarCommands import create_avatar
    from freecad_cloth.avatar.AvatarPoseGui import AvatarPoseTaskPanel
    from freecad_cloth.avatar.SkeletonPose import joint_rotations_from_json

    doc = App.newDocument("AvatarPoseUiAcceptance")
    progress("document-created")
    avatar = create_avatar(attach_collision=False, doc=doc)
    progress("avatar-created")
    doc.recompute()

    panel = AvatarPoseTaskPanel(avatar)
    progress("panel-created")
    runtime = _runtime_diagnostics()
    progress("runtime=" + repr(runtime))
    progress("avatar-joint-pose=" + str(getattr(avatar, "JointPoseJSON", "")))
    from freecad_cloth.avatar import AvatarCommands, AvatarModel, HierarchicalPose

    progress(
        "module-paths="
        + repr(
            {
                "AvatarCommands": getattr(AvatarCommands, "__file__", None),
                "AvatarModel": getattr(AvatarModel, "__file__", None),
                "HierarchicalPose": getattr(HierarchicalPose, "__file__", None),
            }
        )
    )
    progress(
        "fk-code-fingerprint="
        + repr(
            {
                "AvatarCommands.generate_mesh": (
                    getattr(AvatarCommands.generate_mesh, "__module__", None),
                    getattr(AvatarCommands.generate_mesh.__code__, "co_firstlineno", None),
                ),
                "AvatarModel.generate_mesh": (
                    getattr(AvatarModel.generate_mesh, "__module__", None),
                    getattr(AvatarModel.generate_mesh.__code__, "co_firstlineno", None),
                ),
                "HierarchicalPose.generate_hierarchical_mesh": (
                    getattr(HierarchicalPose.generate_hierarchical_mesh.__code__, "co_firstlineno", None),
                ),
            }
        )
    )
    generated_vertices, _, _ = AvatarModel.generate_mesh(panel._staged_parameters())
    progress(
        "generated-mesh-bounds="
        + repr(
            _point_bounds(generated_vertices)
        )
    )
    before_params = panel._staged_parameters()
    progress(
        "staged-params-before-dialog="
        + repr(
            {
                "measurements": dict(before_params.measurements),
                "skin_offset": float(before_params.skin_offset),
                "pose": (
                    before_params.pose.preset,
                    float(before_params.pose.left_arm_angle),
                    float(before_params.pose.right_arm_angle),
                    float(before_params.pose.left_elbow_angle),
                    float(before_params.pose.right_elbow_angle),
                    repr(before_params.pose.joint_rotations),
                ),
            }
        )
    )
    Gui.Control.showDialog(panel)
    after_params = panel._staged_parameters()
    progress(
        "staged-params-after-dialog="
        + repr(
            {
                "measurements": dict(after_params.measurements),
                "skin_offset": float(after_params.skin_offset),
                "pose": (
                    after_params.pose.preset,
                    float(after_params.pose.left_arm_angle),
                    float(after_params.pose.right_arm_angle),
                    float(after_params.pose.left_elbow_angle),
                    float(after_params.pose.right_elbow_angle),
                    repr(after_params.pose.joint_rotations),
                ),
            }
        )
    )
    _events()
    pumped_params = panel._staged_parameters()
    progress(
        "staged-params-after-events="
        + repr(
            {
                "pose": (
                    pumped_params.pose.preset,
                    float(pumped_params.pose.left_arm_angle),
                    float(pumped_params.pose.right_arm_angle),
                    float(pumped_params.pose.left_elbow_angle),
                    float(pumped_params.pose.right_elbow_angle),
                    repr(pumped_params.pose.joint_rotations),
                ),
                "gizmo_dragging": bool(getattr(panel.controller, "_gizmo_dragging", False)),
                "selected_bone": getattr(panel.controller, "selected_bone", None),
            }
        )
    )
    progress("panel-shown")
    view = Gui.activeDocument().activeView()
    if not getattr(panel.form, "isVisible", lambda: False)():
        raise RuntimeError("Pose Mode task panel did not become visible")
    progress("controller-activated")
    if panel.controller.view is None:
        raise RuntimeError("Pose Mode did not activate a FreeCAD 3D view")
    if panel.controller.gizmo is None:
        raise RuntimeError("Pose Mode did not create a usable pose control")
    progress(
        "pivy-coin-loaded-before-capability=%s"
        % ("pivy.coin" in sys.modules)
    )
    fallback = getattr(panel.controller.gizmo, "is_fallback", False)
    runtime_error = getattr(panel.controller, "viewport_runtime_error", None)
    progress(
        "viewport-capability gizmo_mode=%s gizmo_style=%s gizmo_style_error=%r fallback=%s runtime_error=%r"
        % (
            getattr(panel.controller, "gizmo_mode", None),
            getattr(panel.controller, "gizmo_style", None),
            getattr(panel.controller, "gizmo_style_error", None),
            fallback,
            runtime_error,
        )
    )
    if fallback:
        raise RuntimeError(
            "Pose Mode did not activate the native Coin/Pivy viewport path: "
            + str(runtime_error)
        )
    gizmo_mode = panel.controller.gizmo_mode or "unknown"
    if panel.controller.gizmo_mode != "native" or panel.controller.gizmo_style != "axis-rings-cones":
        raise RuntimeError(
            "Pose Mode did not install the required native axis-ring/cone gizmo "
            f"(mode={gizmo_mode!r}, style={getattr(panel.controller, 'gizmo_style', None)!r}, "
            f"error={getattr(panel.controller, 'gizmo_style_error', None)!r})"
        )
    if panel.controller.overlay is None or panel.controller.overlay.getNumChildren() < 2:
        raise RuntimeError("Pose Mode did not install the visible joint/bone overlay")
    from freecad_cloth.avatar.SkeletonPose import CONTROLLABLE_BONES

    visible_bones = len(panel.controller._skeleton_segments)
    if visible_bones <= len(CONTROLLABLE_BONES):
        raise RuntimeError(
            "Pose Mode overlay does not contain the complete authored skeleton "
            f"(visible={visible_bones}, controllable={len(CONTROLLABLE_BONES)})"
        )
    if panel.controller.gizmo_separator is None or panel.controller.gizmo_transform is None:
        raise RuntimeError("Pose Mode did not install the selected-joint gizmo scene nodes")
    from freecad_cloth.avatar.HierarchicalPose import _manual_pose_state
    from freecad_cloth.avatar.HumanoidMesh import load_makehuman_mesh

    expected_mesh, _ = _manual_pose_state(
        panel._staged_parameters(),
        load_makehuman_mesh(),
    )
    actual_points = tuple(avatar.Mesh.Points)
    progress("expected-mesh-bounds=" + repr(_point_bounds(expected_mesh.vertices)))
    progress(
        "actual-mesh-bounds="
        + repr(_point_bounds((point.x, point.y, point.z) for point in actual_points))
    )
    if len(actual_points) != len(expected_mesh.vertices):
        raise RuntimeError(
            "Pose Mode mesh vertex count does not match the authored FK mesh"
        )

    # First prove the public generator and independent FK builder agree before
    # crossing into FreeCAD's native Mesh representation.
    generated_records = _point_records(generated_vertices, precision=7)
    expected_records = _point_records(expected_mesh.vertices, precision=7)
    if [item[0] for item in generated_records] != [item[0] for item in expected_records]:
        raise RuntimeError(
            "Public avatar mesh generator differs from the independent authored FK result"
        )

    actual_values = tuple(
        (point.x, point.y, point.z) for point in actual_points
    )
    max_vertex_error, mismatch = _match_native_points(
        expected_mesh.vertices,
        actual_values,
        tolerance=0.002,
    )
    progress(
        "mesh-fk-consistency-max-error=%.9f mm (native point-match tolerance=0.002 mm)"
        % max_vertex_error
    )
    if mismatch is not None:
        mismatch_index, expected_point, nearest_point, nearest_error = mismatch
        raise RuntimeError(
            "Pose Mode native mesh differs from authored FK coordinates "
            "(first unmatched expected point index=%s expected=%r nearest=%r "
            "distance=%.9f mm, tolerance=0.002 mm)"
            % (
                mismatch_index,
                expected_point,
                nearest_point,
                nearest_error,
            )
        )
    panel.controller.select_joint("upperarm01.L")
    if str(panel.skeleton_joint_index) != "upperarm01.L":
        raise RuntimeError("Pose Mode failed to select the screenshot fixture shoulder joint")
    if panel.joint_list_widget.isVisible():
        raise RuntimeError("Pose Mode exposed the joint-list fallback by default")
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    if panel.form.findChildren(QtWidgets.QSlider):
        raise RuntimeError("Pose Mode retained redundant slider-based primary controls")
    panel.symmetry.setChecked(True)
    panel.angle_snap.setChecked(True)
    panel.joint_list_toggle.setChecked(True)
    _events()
    if not panel.joint_list_widget.isVisible():
        raise RuntimeError("Pose Mode Joint list fallback did not expand")
    panel.joint_list_toggle.setChecked(False)
    _events()
    metrics = _capture_pose_screen(
        Path("artifacts/avatar-pose-mode.png"),
        panel,
        view,
    )
    progress(
        "screenshot=artifacts/avatar-pose-mode.png width=%d height=%d opaque_pixels=%d "
        "nonwhite_pixels=%d distinct_rgb=%d"
        % (
            metrics["width"],
            metrics["height"],
            metrics["opaque_pixels"],
            metrics["nonwhite_pixels"],
            metrics["distinct_rgb"],
        )
    )

    selected = str(panel.skeleton_joint_index)
    if not selected:
        raise RuntimeError("Pose Mode did not select a default joint")

    # Pivy mouse callbacks are unavailable in this FreeCAD/SWIG build.
    # Select the joint through the controller API, then edit Exact angles using
    # real Qt keyboard events and capture the resulting live UI/model preview.
    # The preceding screenshot helper has already sized and activated the main window.
    # Do not resize it again here: some FreeCAD task-panel builds recreate child widgets.
    window = Gui.getMainWindow()
    if window is None or not window.isVisible():
        raise RuntimeError("FreeCAD main window is unavailable for Pose Mode GIF recording")
    panel.controller.select_joint("upperarm01.L")
    _events()
    recorder = UiGifRecorder(
        "artifacts/ui-gifs/pose-joint-rotation.gif",
        gui=Gui,
        window=window,
        fps=12,
        scale=0.5,
        max_frames=110,
        show_cursor=False,
    )
    recorder.start()
    try:
        recorder.hold(600)
        click_widget(panel.precision)
        _events()
        recorder.hold(450)
        field = panel.precision_fields["y"]
        type_text(field, "35", replace_selection=True)
        # Return activates FreeCAD's task-panel default button in headless CI.
        # Commit the spin-box edit by leaving the field instead of accepting
        # the whole Pose Mode dialog.
        field.clearFocus()
        _events()
        wait_until(
            lambda: (
                panel._staged_joint_rotations.get("upperarm01.L") is not None
                and abs(
                    float(panel._staged_joint_rotations["upperarm01.L"].y) - 35.0
                ) < 1e-4
            ),
            description="keyboard-edited upper-arm joint rotation",
        )
        recorder.hold(900)
        pose_after_edit = panel._staged_joint_rotations.get("upperarm01.L")
        if pose_after_edit is None or abs(float(pose_after_edit.y) - 35.0) > 1e-4:
            raise RuntimeError("Exact angles keyboard input did not stage the expected rotation")
    finally:
        if recorder._started:
            recorder.stop()


    before = _bounds(avatar.Mesh)
    panel._stage_joint_rotation(
        "upperarm01.L",
        0.0,
        -35.0,
        0.0,
        preview=True,
        snap=True,
    )
    after = _bounds(avatar.Mesh)
    if before == after:
        raise RuntimeError("interactive pose preview did not change mannequin geometry")

    staged = panel._staged_joint_rotations
    left = staged.get("upperarm01.L")
    right = staged.get("upperarm01.R")
    if left is None or right is None:
        raise RuntimeError("symmetry did not stage both shoulder joints")
    if float(left.y) != -35.0 or float(right.y) != 35.0:
        raise RuntimeError("symmetry produced the wrong mirrored shoulder rotation")

    panel.angle_snap.setChecked(True)
    panel._stage_joint_rotation(
        "lowerarm01.L",
        0.0,
        41.0,
        0.0,
        preview=False,
        snap=False,
    )
    exact = panel._staged_joint_rotations.get("lowerarm01.L")
    if exact is None or float(exact.y) != 41.0:
        raise RuntimeError("Exact angle fallback unexpectedly inherited 5 degree snapping")

    panel.accept()
    persisted_payload = str(avatar.JointPoseJSON)
    persisted = joint_rotations_from_json(persisted_payload)
    persisted_bones = {rotation.bone for rotation in persisted}
    if not {"upperarm01.L", "upperarm01.R"} <= persisted_bones:
        raise RuntimeError("accepted pose was not persisted in JointPoseJSON")

    panel2 = AvatarPoseTaskPanel(avatar)
    panel2._stage_joint_rotation(
        "lowerarm01.L",
        0.0,
        45.0,
        0.0,
        preview=True,
    )
    if str(avatar.JointPoseJSON) != persisted_payload:
        raise RuntimeError("preview unexpectedly mutated persistent JointPoseJSON")
    panel2.reject()
    if str(avatar.JointPoseJSON) != persisted_payload:
        raise RuntimeError("Cancel failed to restore persistent pose state")
    if panel2.controller.view is not None or panel2.controller.gizmo is not None:
        raise RuntimeError("Cancel failed to remove Pose Mode viewport state")

    Path("artifacts").mkdir(parents=True, exist_ok=True)
    Path("artifacts/avatar-pose-ui.log").write_text(
        f"avatar-pose-ui=passed gizmo={gizmo_mode} preview=true symmetry=true persistent=true\n"
        "avatar-pose-ui-cancel=passed restored=true cleanup=true\n",
        encoding="utf-8",
    )
    print(
        f"avatar-pose-ui=passed gizmo={gizmo_mode} preview=true symmetry=true persistent=true",
        flush=True,
    )
    print("avatar-pose-ui-cancel=passed restored=true cleanup=true", flush=True)
    App.closeDocument(doc.Name)
    trace.close()


try:
    run()
except BaseException as exc:
    Path("artifacts").mkdir(parents=True, exist_ok=True)
    Path("artifacts/avatar-pose-ui.log").write_text(
        "avatar-pose-ui=failed\n"
        + repr(exc)
        + "\n"
        + traceback.format_exc(),
        encoding="utf-8",
    )
    print("avatar-pose-ui=failed", exc, flush=True)
    App.Console.PrintError("Avatar Pose UI acceptance failed: %s\n" % exc)
    os._exit(1)
os._exit(0)
