"""Real FreeCAD/Xvfb acceptance for the focused mannequin Pose Mode UI."""

import faulthandler
import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import FreeCAD as App
import FreeCADGui as Gui



def _capture_screen(path):
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    app = QtWidgets.QApplication.instance()
    if app is None or app.primaryScreen() is None:
        raise RuntimeError("Qt primary screen is unavailable for Pose Mode screenshot")
    if not app.primaryScreen().grabWindow(0).save(path):
        raise RuntimeError("failed to save Pose Mode UI screenshot")


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
    from freecad_cloth.avatar.SkeletonPose import joint_rotations_from_json

    doc = App.newDocument("AvatarPoseUiAcceptance")
    progress("document-created")
    avatar = create_avatar(attach_collision=False, doc=doc)
    progress("avatar-created")
    doc.recompute()

    panel = AvatarPoseTaskPanel(avatar)
    progress("panel-created")
    Gui.Control.showDialog(panel)
    progress("panel-shown")
    view = Gui.activeDocument().activeView()
    view.viewIsometric()
    view.fitAll()
    Gui.updateGui()
    progress("controller-activated")
    if panel.controller.view is None:
        raise RuntimeError("Pose Mode did not activate a FreeCAD 3D view")
    if panel.controller.gizmo is None:
        raise RuntimeError("Pose Mode did not create a usable pose control")

    selected = str(panel.skeleton_joint_index)
    if not selected:
        raise RuntimeError("Pose Mode did not select a default joint")

    before = _bounds(avatar.Mesh)
    panel._stage_joint_rotation(
        "upperarm01.L",
        0.0,
        -35.0,
        0.0,
        preview=True,
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

    gizmo_mode = "fallback" if getattr(panel.controller.gizmo, "is_fallback", False) else "native"
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
