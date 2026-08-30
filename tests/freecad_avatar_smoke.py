"""Real FreeCAD runtime smoke coverage for the parametric mannequin."""
import sys
from pathlib import Path
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import FreeCAD as App
from AvatarCommands import create_avatar, set_avatar_measurements, set_avatar_pose, set_avatar_skin_offset


def main():
    doc = App.newDocument("ClothAvatarSmoke")
    avatar = create_avatar()
    assert avatar.AvatarType == "ClothAvatar"
    assert avatar.Shape.Volume > 0
    assert avatar.AvatarStatus == "Valid"
    original_volume = avatar.Shape.Volume
    set_avatar_measurements(chest=1100)
    assert avatar.Shape.Volume != original_volume
    set_avatar_pose("sewing")
    set_avatar_skin_offset(6.0)
    assert avatar.PosePreset == "sewing"
    assert abs(float(avatar.SkinOffset) - 6.0) < 1e-9
    assert avatar.CollisionProxy is not None
    doc.recompute()
    with tempfile.TemporaryDirectory() as directory:
        path = str(Path(directory) / "avatar.FCStd")
        doc.saveAs(path)
        App.closeDocument(doc.Name)
        reopened = App.openDocument(path)
        restored = reopened.getObject("ClothAvatar")
        assert restored is not None
        assert restored.AvatarStatus == "Valid"
        assert restored.PosePreset == "sewing"
        assert abs(float(restored.Chest) - 1100.0) < 1e-9
        assert abs(float(restored.SkinOffset) - 6.0) < 1e-9
        App.closeDocument(reopened.Name)
    print("FreeCAD parametric avatar smoke test passed")


if __name__ == "__main__":
    main()
