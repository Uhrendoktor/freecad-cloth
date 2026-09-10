import os
import sys

import FreeCAD as App
import FreeCADGui as Gui

ROOT = "/workspace"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from freecad_cloth.simulation.SimulationQualityRuntimeV2 import create_quality_simulation_scene


def main():
    os.makedirs("artifacts/hosted-avatar", exist_ok=True)
    doc = App.newDocument("HostedAvatarVisual")
    scene = create_quality_simulation_scene(doc)
    avatar = scene.AvatarProxy.SourceObject
    if avatar is None or str(getattr(avatar, "AvatarType", "")) != "ClothAvatar":
        raise RuntimeError("production ClothAvatar was not created")
    if int(getattr(avatar, "MeshVertexCount", 0)) <= 100 or int(getattr(avatar, "MeshTriangleCount", 0)) <= 100:
        raise RuntimeError("avatar mesh is not a real humanoid mesh")
    doc.recompute()
    view = Gui.activeDocument().activeView()
    view.setCameraType("Orthographic")
    view.viewFront()
    view.fitAll()
    Gui.updateGui()
    app = Gui.getMainWindow()
    if app is None:
        raise RuntimeError("FreeCAD main window unavailable")
    app.show()
    app.resize(1280, 720)
    Gui.updateGui()
    image = app.grab()
    path = "artifacts/hosted-avatar/avatar-front.png"
    if image.isNull() or image.size().width() != 1280 or image.size().height() != 720:
        raise RuntimeError("invalid avatar capture size")
    if not image.save(path):
        raise RuntimeError("failed to save avatar capture")
    if os.path.getsize(path) < 20000:
        raise RuntimeError("avatar capture is suspiciously small")
    print("AVATAR_BOUNDS", avatar.Mesh.BoundBox.XMin, avatar.Mesh.BoundBox.XMax, avatar.Mesh.BoundBox.YMin, avatar.Mesh.BoundBox.YMax, avatar.Mesh.BoundBox.ZMin, avatar.Mesh.BoundBox.ZMax)
    print("CAPTURE", path)


main()
