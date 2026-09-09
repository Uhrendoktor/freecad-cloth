"""Canonical FreeCAD/Xvfb acceptance for avatar provider lifecycle."""
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
import Part


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
        raise RuntimeError("avatar task panel did not become visible")


def run_acceptance():
    from freecad_cloth.avatar.AvatarCommands import create_avatar
    from freecad_cloth.avatar.AvatarGui import AvatarTaskPanel
    from freecad_cloth.simulation.DrapeTarget import refresh_drape_target, target_status

    doc = App.newDocument("AvatarProviderAcceptance")
    path = None
    try:
        source = doc.addObject("Part::Feature", "ProviderAcceptanceBody")
        source.Label = "Provider Acceptance Body"
        source.Shape = Part.makeCylinder(35, 180, App.Vector(0, 0, 0))
        doc.recompute()

        avatar = create_avatar()
        target = doc.getObject("DrapeTarget")
        if target is None:
            raise RuntimeError("avatar creation did not create a persistent DrapeTarget")
        if target_status(target)["state"] != "ready":
            raise RuntimeError("new mannequin target is not ready")
        identity = avatar.Name
        initial_revision = int(avatar.AvatarRevision)

        panel = AvatarTaskPanel(avatar)
        _show_panel(panel)
        if panel.provider.currentText() != "MakeHuman HM08 humanoid mesh":
            raise RuntimeError("avatar task panel did not load the persistent default provider")
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(source)
        panel._use_selected_provider_source()
        if panel.provider.currentText() != "FreeCAD body / imported geometry":
            raise RuntimeError("task panel did not stage the FreeCAD provider")
        if panel.provider_source_label.text() != "Source: Provider Acceptance Body":
            raise RuntimeError("task panel did not show the staged FreeCAD provider source")
        if not panel._apply():
            raise RuntimeError("avatar provider swap was not applied")
        _close_task()
        avatar = doc.getObject(identity)
        target = doc.getObject("DrapeTarget")
        if avatar is None or target is None:
            raise RuntimeError("provider swap replaced or lost the persistent avatar/target")
        if avatar.Name != identity or str(avatar.AvatarProviderId) != "freecad-geometry":
            raise RuntimeError("FreeCAD provider swap did not persist on the avatar object")
        if avatar.ProviderSource != source:
            raise RuntimeError("FreeCAD provider source link did not persist in the document")
        provider_revision = int(avatar.AvatarRevision)
        if provider_revision <= initial_revision:
            raise RuntimeError("provider swap did not advance AvatarRevision")
        if target_status(target)["state"] != "stale":
            raise RuntimeError("provider swap did not deterministically invalidate DrapeTarget")

        refresh_drape_target(target)
        if target_status(target)["state"] != "ready":
            raise RuntimeError("explicit DrapeTarget refresh did not repair provider swap state")

        panel = AvatarTaskPanel(avatar)
        _show_panel(panel)
        panel.pose.setCurrentText("sewing")
        if not panel._apply():
            raise RuntimeError("avatar pose edit was not applied")
        _close_task()
        avatar = doc.getObject(identity)
        target = doc.getObject("DrapeTarget")
        pose_revision = int(avatar.AvatarRevision)
        if pose_revision <= provider_revision:
            raise RuntimeError("pose change did not advance AvatarRevision")
        if target_status(target)["state"] != "stale":
            raise RuntimeError("pose change did not deterministically invalidate DrapeTarget")

        fd, path = tempfile.mkstemp(prefix="cloth-avatar-provider-", suffix=".FCStd")
        os.close(fd)
        doc.recompute()
        doc.saveAs(path)
        App.closeDocument(doc.Name)
        doc = None
        reloaded = App.openDocument(path)
        reloaded.recompute()
        avatar = reloaded.getObject(identity)
        target = reloaded.getObject("DrapeTarget")
        restored_source = reloaded.getObject("ProviderAcceptanceBody")
        if avatar is None or target is None or restored_source is None:
            raise RuntimeError("avatar provider state did not survive save/reload")
        if str(avatar.AvatarProviderId) != "freecad-geometry":
            raise RuntimeError("provider identity was lost across save/reload")
        if avatar.ProviderSource != restored_source:
            raise RuntimeError("provider source link was lost across save/reload")
        if int(avatar.AvatarRevision) != pose_revision:
            raise RuntimeError("AvatarRevision was not persisted across save/reload")
        if str(avatar.PosePreset) != "sewing":
            raise RuntimeError("avatar pose was not persisted across save/reload")
        if target_status(target)["state"] != "stale":
            raise RuntimeError("stale DrapeTarget state was not preserved across save/reload")

        refresh_drape_target(target)
        if target_status(target)["state"] != "ready":
            raise RuntimeError("reloaded avatar target could not be explicitly refreshed")
        _close_task()
        App.closeDocument(reloaded.Name)
    finally:
        if doc is not None and doc.Name in App.listDocuments():
            App.closeDocument(doc.Name)
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass


if __name__ == "__main__":
    run_acceptance()
    print("avatar provider acceptance passed")
