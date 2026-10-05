"""Real FreeCAD/Xvfb acceptance for the focused mannequin Pose Mode UI."""

import sys

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
    from freecad_cloth.avatar.AvatarCommands import create_avatar
    from freecad_cloth.avatar.AvatarPoseGui import AvatarPoseTaskPanel
    from freecad_cloth.avatar.SkeletonPose import joint_rotations_from_json

    doc = App.newDocument("AvatarPoseUiAcceptance")
    avatar = create_avatar(attach_collision=False, doc=doc)
    doc.recompute()

    panel = AvatarPoseTaskPanel(avatar)
    Gui.Control.showDialog(panel)
    view = Gui.activeDocument().activeView()
    view.viewIsometric()
    view.fitAll()
    Gui.updateGui()
    if panel.controller.view is None:
        raise RuntimeError("Pose Mode did not activate a FreeCAD 3D view")
    if panel.controller.gizmo is None:
        raise RuntimeError("Pose Mode did not create the rotation trackball")

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
    if float(left.y) != -35.0 or float(right.y) != -35.0:
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

    print("avatar-pose-ui=passed gizmo=true preview=true symmetry=true persistent=true")
    print("avatar-pose-ui-cancel=passed restored=true cleanup=true")
    doc.close()


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print("avatar-pose-ui=failed", exc)
        App.Console.PrintError("Avatar Pose UI acceptance failed: %s\n" % exc)
        sys.exit(1)
