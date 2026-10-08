"""Real FreeCAD/Xvfb acceptance for the focused mannequin Pose Mode UI."""

import faulthandler
import math
import os
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
    click_viewport,
    focus_main_window,
    mouse_move,
    mouse_press,
    mouse_release,
    viewport_widget,
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
    from freecad_cloth.avatar.SkeletonPose import JointRotation, joint_rotations_from_json

    doc = App.newDocument("AvatarPoseUiAcceptance")
    progress("document-created")
    avatar = create_avatar(attach_collision=False, doc=doc)
    progress("avatar-created")
    doc.recompute()

    panel = AvatarPoseTaskPanel(avatar)
    progress("panel-created")
    runtime = _runtime_diagnostics()
    progress("runtime=" + repr(runtime))
    Gui.Control.showDialog(panel)
    _events()
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
        "viewport-capability gizmo_mode=%s fallback=%s runtime_error=%r"
        % (getattr(panel.controller, "gizmo_mode", None), fallback, runtime_error)
    )
    if fallback:
        raise RuntimeError(
            "Pose Mode did not activate the native Coin/Pivy viewport path: "
            + str(runtime_error)
        )
    gizmo_mode = panel.controller.gizmo_mode or "unknown"
    if panel.controller.gizmo_mode not in {"native", "trackball-fallback"}:
        raise RuntimeError(
            "Pose Mode did not select a supported interactive gizmo mode"
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

    # Prove the actual viewport event path: select a different joint by mouse,
    # then drag the native rotation ring and assert staged pose state changes.
    window = focus_main_window(Gui, size=(1280, 720))
    viewport = viewport_widget(Gui, view)
    panel.controller.select_joint("lowerarm01.L")
    _events()
    recorder = UiGifRecorder(
        "artifacts/ui-gifs/pose-joint-rotation.gif",
        gui=Gui,
        window=window,
        fps=7,
        scale=0.5,
        max_frames=110,
    )
    recorder.start()
    recorder.hold(600)
    segment = panel.controller._skeleton_segments["upperarm01.L"]
    midpoint = tuple(
        (float(segment[0][index]) + float(segment[1][index])) * 0.5
        for index in range(3)
    )
    click_viewport(
        viewport,
        panel.controller._screen_position(midpoint),
        gui=Gui,
    )
    wait_until(
        lambda: panel.controller.selected_bone == "upperarm01.L",
        description="mouse selection of the upper-arm bone",
    )
    recorder.hold(650)
    pose_before_drag = panel._staged_joint_rotations.get(
        "upperarm01.L", JointRotation("upperarm01.L")
    )
    center = panel.controller._screen_position(
        panel.controller._positions["upperarm01.L"]
    )
    ring_start = (center[0] + 31.0, center[1])
    mouse_press(viewport, ring_start)
    try:
        wait_until(
            lambda: panel.controller._gizmo_dragging,
            timeout_seconds=1.2,
            description="native rotation ring drag start",
        )
    except TimeoutError as exc:
        mouse_release(viewport, ring_start)
        recorder.stop()
        raise RuntimeError(
            "a real click near the rotation ring did not start native gizmo dragging"
        ) from exc
    for index in range(1, 13):
        angle = (math.pi * 0.5) * index / 12.0
        point = (
            center[0] + 31.0 * math.cos(angle),
            center[1] - 31.0 * math.sin(angle),
        )
        mouse_move(viewport, point, delay_ms=30, buttons_down=True)
    mouse_release(viewport, (center[0], center[1] - 31.0))
    recorder.hold(700)
    pose_after_drag = panel._staged_joint_rotations.get("upperarm01.L")
    if pose_after_drag is None or pose_before_drag is None:
        recorder.stop()
        raise RuntimeError("native gizmo drag did not stage the selected joint rotation")
    before_angles = (pose_before_drag.x, pose_before_drag.y, pose_before_drag.z)
    after_angles = (pose_after_drag.x, pose_after_drag.y, pose_after_drag.z)
    if all(
        abs(float(left) - float(right)) < 1e-4
        for left, right in zip(before_angles, after_angles, strict=True)
    ):
        recorder.stop()
        raise RuntimeError("native gizmo mouse drag did not change staged joint rotation")
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
