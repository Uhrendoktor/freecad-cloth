# Copyright (C) 2026 FreeCAD Cloth contributors
"""Canonical FreeCAD/Xvfb acceptance for avatar provider lifecycle."""

import contextlib
import faulthandler
import json
import os
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import FreeCAD as App
import FreeCADGui as Gui


def _events():
    Gui.updateGui()
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    QtWidgets.QApplication.processEvents()


def _close_task():
    if Gui.Control.activeDialog():
        Gui.Control.closeDialog()
        _events()


def _show_panel(panel):
    Gui.Control.showDialog(panel)
    _events()
    if not panel.form.isVisible():
        panel.form.show()
        panel.form.setVisible(True)
        panel.form.raise_()
        _events()
    if not panel.form.isVisible() and not panel.form.isVisibleTo(Gui.getMainWindow()):
        msg = "avatar task panel did not become visible"
        raise RuntimeError(msg)


def _progress(message):
    trace = globals().get("_TRACE_HANDLE")
    if trace is None:
        return
    trace.write(str(message) + "\n")
    trace.flush()


def _mesh_topology(mesh):
    topology = getattr(mesh, "Topology", None)
    if topology is None:
        msg = "avatar mesh topology is unavailable"
        raise RuntimeError(msg)
    vertices, triangles = topology
    return tuple(tuple(float(c) for c in vertex) for vertex in vertices), tuple(
        tuple(int(i) for i in tri) for tri in triangles
    )


_TRACE_PATH = Path("artifacts/avatar-acceptance-progress.log")
_TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
_TRACE_HANDLE = _TRACE_PATH.open("w", encoding="utf-8", buffering=1)
try:
    faulthandler.enable(file=_TRACE_HANDLE, all_threads=True)
    faulthandler.dump_traceback_later(30.0, repeat=True, file=_TRACE_HANDLE)
except (AttributeError, OSError, RuntimeError):
    pass


def run_acceptance():
    _progress("start")
    from freecad_cloth.avatar.avatar_commands import create_avatar
    from freecad_cloth.avatar.AvatarGui import AvatarTaskPanel
    from freecad_cloth.avatar.AvatarVisualSanity import inspect_avatar_mesh
    from freecad_cloth.simulation.DrapeTarget import refresh_drape_target, target_status

    _progress("before-document")
    doc = App.newDocument("AvatarProviderAcceptance")
    path = None
    try:
        import Part

        _progress("part-imported")
        source = doc.addObject("Part::Feature", "ProviderAcceptanceBody")
        _progress("document-created")
        source.Label = "Provider Acceptance Body"
        source.Shape = Part.makeCylinder(35, 180, App.Vector(0, 0, 0))
        doc.recompute()

        _progress("before-create-avatar")
        avatar = create_avatar()
        _progress("after-create-avatar")
        _progress("before-target-lookup")
        target = doc.getObject("DrapeTarget")
        _progress(f"after-target-lookup:{target is not None}")
        if target is None:
            msg = "avatar creation did not create a persistent DrapeTarget"
            raise RuntimeError(msg)
        _progress("before-target-status")
        status = target_status(target)
        _progress(f"after-target-status:{status}")
        if status["state"] != "ready":
            msg = f"new mannequin target is not ready: {status}"
            raise RuntimeError(msg)
        _progress("before-avatar-mesh-lookup")
        avatar_mesh = getattr(avatar, "Mesh", None)
        _progress(f"after-avatar-mesh-lookup:{avatar_mesh is not None}")
        if avatar_mesh is None:
            msg = "generated mannequin has no mesh"
            raise RuntimeError(msg)
        _progress("before-mesh-topology")
        vertices, triangles = _mesh_topology(avatar_mesh)
        _progress(f"after-mesh-topology:vertices={len(vertices)} triangles={len(triangles)}")
        _progress("before-mesh-sanity")
        sanity = inspect_avatar_mesh(
            vertices, triangles, expected_height=float(getattr(avatar, "Height", 1750.0))
        )
        _progress(f"after-mesh-sanity:{sanity}")
        if sanity.triangle_count < 100:
            msg = "generated mannequin mesh is implausibly small"
            raise RuntimeError(msg)
        identity = avatar.Name

        baseline_vertices, baseline_triangles = _mesh_topology(avatar.Mesh)
        baseline_landmarks = {
            str(item).split("|", 1)[0]: str(item).split("|", 1)[1]
            for item in getattr(avatar, "Landmarks", [])
            if "|" in str(item)
        }
        _progress("before-manual-pose-panel")
        panel = AvatarTaskPanel(avatar)
        _show_panel(panel)
        _progress("manual-pose-panel-shown")
        upperarm_index = panel.skeleton_joint.findText("Left shoulder")
        if upperarm_index < 0:
            msg = "manual skeleton editor did not expose the left shoulder joint"
            raise RuntimeError(msg)
        panel.skeleton_joint.setCurrentIndex(upperarm_index)
        panel.skeleton_y.setValue(25.0)
        if not panel.skeleton_symmetry.isChecked():
            msg = "manual skeleton editor did not enable symmetry by default"
            raise RuntimeError(msg)
        staged_pose = json.loads(panel._staged_parameters().to_json())
        joints = staged_pose["pose"]["joints"]
        if joints["upperarm01.L"]["y"] != 25.0 or joints["upperarm01.R"]["y"] != -25.0:
            msg = "manual skeleton symmetry did not mirror the shoulder rotation"
            raise RuntimeError(msg)
        if not panel._apply():
            msg = f"manual skeleton joint edit was not applied; status={panel.status.text()!r}"
            raise RuntimeError(msg)
        _progress("manual-pose-applied")
        _close_task()
        avatar = doc.getObject(identity)
        target = doc.getObject("DrapeTarget")
        posed_vertices, posed_triangles = _mesh_topology(avatar.Mesh)
        if posed_vertices == baseline_vertices or posed_triangles != baseline_triangles:
            msg = "manual skeleton rotation did not deform the mannequin mesh"
            raise RuntimeError(msg)
        joint_payload = json.loads(str(avatar.JointPoseJSON))
        if joint_payload["joints"]["upperarm01.L"]["y"] != 25.0:
            msg = "manual skeleton rotation was not persisted"
            raise RuntimeError(msg)
        posed_landmarks = {
            str(item).split("|", 1)[0]: str(item).split("|", 1)[1]
            for item in getattr(avatar, "Landmarks", [])
            if "|" in str(item)
        }
        if posed_landmarks.get("wrist_left") == baseline_landmarks.get("wrist_left"):
            msg = "manual skeleton rotation did not update the persisted wrist landmark"
            raise RuntimeError(msg)
        if target_status(target)["state"] != "stale":
            msg = "manual skeleton edit did not deterministically invalidate DrapeTarget"
            raise RuntimeError(msg)

        refresh_drape_target(target)
        panel = AvatarTaskPanel(avatar)
        _show_panel(panel)
        panel._reset_skeleton_pose()
        if not panel._apply():
            msg = f"manual skeleton reset was not applied; status={panel.status.text()!r}"
            raise RuntimeError(msg)
        _progress("manual-pose-reset")
        _close_task()
        avatar = doc.getObject(identity)
        if str(avatar.JointPoseJSON) != '{"joints":{},"schema_version":1,"units":"deg"}':
            msg = "manual skeleton reset did not clear persistent joint rotations"
            raise RuntimeError(msg)
        reset_vertices, reset_triangles = _mesh_topology(avatar.Mesh)
        if reset_vertices != baseline_vertices or reset_triangles != baseline_triangles:
            msg = "manual skeleton reset did not restore the baseline mannequin"
            raise RuntimeError(msg)
        target = doc.getObject("DrapeTarget")
        refresh_drape_target(target)

        panel = AvatarTaskPanel(avatar)
        _show_panel(panel)
        if not panel.provider_buttons["makehuman-hm08"].isChecked():
            msg = "avatar task panel did not load the persistent default provider"
            raise RuntimeError(msg)
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(source)
        panel._use_selected_provider_source()
        if not panel.provider_buttons["freecad-geometry"].isChecked():
            msg = "task panel did not stage the FreeCAD provider"
            raise RuntimeError(msg)
        if panel.provider_source_label.text() != "Source: Provider Acceptance Body":
            msg = "task panel did not show the staged FreeCAD provider source"
            raise RuntimeError(msg)
        if not panel._apply():
            msg = f"avatar provider swap was not applied; status={panel.status.text()!r}"
            raise RuntimeError(msg)
        _progress("provider-swap-applied")
        _close_task()
        avatar = doc.getObject(identity)
        target = doc.getObject("DrapeTarget")
        if avatar is None or target is None:
            msg = "provider swap replaced or lost the persistent avatar/target"
            raise RuntimeError(msg)
        if avatar.Name != identity or str(avatar.AvatarProviderId) != "freecad-geometry":
            msg = "FreeCAD provider swap did not persist on the avatar object"
            raise RuntimeError(msg)
        if avatar.ProviderSource != source:
            msg = "FreeCAD provider source link did not persist in the document"
            raise RuntimeError(msg)
        if target_status(target)["state"] != "stale":
            msg = "provider swap did not deterministically invalidate DrapeTarget"
            raise RuntimeError(msg)

        refresh_drape_target(target)
        if target_status(target)["state"] != "ready":
            msg = "explicit DrapeTarget refresh did not repair provider swap state"
            raise RuntimeError(msg)

        panel = AvatarTaskPanel(avatar)
        _show_panel(panel)
        panel.pose.setCurrentText("sewing")
        if not panel._apply():
            msg = f"avatar pose edit was not applied; status={panel.status.text()!r}"
            raise RuntimeError(msg)
        _progress("pose-edit-applied")
        _close_task()
        _progress("pose-edit-task-closed")
        avatar = doc.getObject(identity)
        target = doc.getObject("DrapeTarget")
        if str(avatar.PosePreset) != "sewing":
            msg = "pose edit did not persist on the avatar object"
            raise RuntimeError(msg)
        if target_status(target)["state"] != "stale":
            msg = "pose change did not deterministically invalidate DrapeTarget"
            raise RuntimeError(msg)
        _progress("pose-edit-target-stale-verified")
        pose_revision = int(avatar.AvatarRevision)

        fd, path = tempfile.mkstemp(prefix="cloth-avatar-provider-", suffix=".FCStd")
        os.close(fd)
        _progress("before-provider-save-recompute")
        doc.recompute()
        _progress("after-provider-save-recompute")
        doc.saveAs(path)
        _progress("after-provider-save")
        App.closeDocument(doc.Name)
        doc = None
        _progress("provider-doc-closed-for-reload")
        reloaded = App.openDocument(path)
        _progress("provider-doc-opened-from-save")
        reloaded.recompute()
        _progress("provider-document-recomputed-after-reload")
        avatar = reloaded.getObject(identity)
        target = reloaded.getObject("DrapeTarget")
        restored_source = reloaded.getObject("ProviderAcceptanceBody")
        if avatar is None or target is None or restored_source is None:
            msg = "avatar provider state did not survive save/reload"
            raise RuntimeError(msg)
        if str(avatar.AvatarProviderId) != "freecad-geometry":
            msg = "provider identity was lost across save/reload"
            raise RuntimeError(msg)
        if avatar.ProviderSource != restored_source:
            msg = "provider source link was lost across save/reload"
            raise RuntimeError(msg)
        if int(avatar.AvatarRevision) != pose_revision:
            msg = "AvatarRevision was not persisted across save/reload"
            raise RuntimeError(msg)
        if str(avatar.PosePreset) != "sewing":
            msg = "avatar pose was not persisted across save/reload"
            raise RuntimeError(msg)
        if target_status(target)["state"] != "stale":
            msg = "stale DrapeTarget state was not preserved across save/reload"
            raise RuntimeError(msg)
        _progress("provider-document-reload-state-verified")

        refresh_drape_target(target)
        if target_status(target)["state"] != "ready":
            msg = "reloaded avatar target could not be explicitly refreshed"
            raise RuntimeError(msg)
        _progress("provider-document-reloaded-and-target-refreshed")
        _close_task()
        App.closeDocument(reloaded.Name)
    finally:
        if doc is not None and doc.Name in App.listDocuments():
            App.closeDocument(doc.Name)
        if path:
            with contextlib.suppress(OSError):
                Path(path).unlink()


# FreeCAD's macro runner does not preserve the normal CLI __name__ contract.
try:
    run_acceptance()
    print("avatar provider acceptance passed", flush=True)
    os._exit(0)
except BaseException as exc:
    try:
        _progress(f"acceptance-failure:{type(exc).__name__}:{exc!r}")
        _TRACE_HANDLE.write(traceback.format_exc() + "\n")
        _TRACE_HANDLE.flush()
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        pass
    print("avatar provider acceptance failed", repr(exc), flush=True)
    os._exit(1)
