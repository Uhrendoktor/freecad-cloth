"""Real FreeCAD runtime smoke coverage for the humanoid mesh avatar."""
import sys
from pathlib import Path
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import FreeCAD as App
from freecad_cloth.avatar.AvatarCommands import create_avatar, set_avatar_measurements, set_avatar_pose, set_avatar_skin_offset
from freecad_cloth.simulation.DrapeTarget import target_status


def mesh_signature(obj):
    points = list(obj.Mesh.Points)
    sample = tuple((round(float(p.x), 3), round(float(p.y), 3), round(float(p.z), 3)) for p in points[:12])
    return int(obj.Mesh.CountPoints), int(obj.Mesh.CountFacets), sample


def main():
    doc = App.newDocument("ClothAvatarSmoke")
    avatar = create_avatar()
    assert avatar.AvatarType == "ClothAvatar"
    assert avatar.AvatarMeshProvider == "makehuman-hm08"
    assert avatar.Mesh.CountPoints > 100
    assert avatar.Mesh.CountFacets > 100
    assert avatar.AvatarStatus == "Valid"
    assert avatar.ArrangementPoints
    expected_arrangement = list(avatar.ArrangementPoints)
    arrangement_names = [str(item).split("|", 1)[0] for item in expected_arrangement]
    assert arrangement_names == [
        "neck", "chest", "waist", "hip",
        "shoulder_left", "shoulder_right", "knee_left", "knee_right",
    ]
    assert avatar.DrapeTarget is not None
    assert avatar.DrapeTarget.TargetType == "Mannequin"
    assert target_status(avatar.DrapeTarget)["state"] == "ready"
    original_mesh = mesh_signature(avatar)
    set_avatar_measurements(chest=1100)
    assert mesh_signature(avatar) != original_mesh
    assert list(avatar.ArrangementPoints) == expected_arrangement
    assert target_status(avatar.DrapeTarget)["state"] == "ready"
    set_avatar_pose("sewing")
    set_avatar_skin_offset(6.0)
    assert avatar.PosePreset == "sewing"
    assert abs(float(avatar.SkinOffset) - 6.0) < 1e-9
    assert avatar.CollisionProxy is not None
    assert avatar.DrapeTarget is not None
    assert target_status(avatar.DrapeTarget)["state"] == "ready"
    doc.recompute()
    with tempfile.TemporaryDirectory() as directory:
        path = str(Path(directory) / "avatar.FCStd")
        doc.saveAs(path)
        App.closeDocument(doc.Name)
        reopened = App.openDocument(path)
        restored = reopened.getObject("ClothAvatar")
        assert restored is not None
        assert restored.AvatarStatus == "Valid"
        assert restored.AvatarMeshProvider == "makehuman-hm08"
        assert restored.PosePreset == "sewing"
        assert abs(float(restored.Chest) - 1100.0) < 1e-9
        assert abs(float(restored.SkinOffset) - 6.0) < 1e-9
        assert list(restored.ArrangementPoints) == expected_arrangement
        assert list(restored.Landmarks)
        assert restored.Mesh.CountPoints > 100
        assert restored.Mesh.CountFacets > 100
        assert restored.DrapeTarget is not None
        assert restored.DrapeTarget.TargetType == "Mannequin"
        assert target_status(restored.DrapeTarget)["state"] == "ready"
        App.closeDocument(reopened.Name)
    print("FreeCAD humanoid mesh avatar smoke test passed")


if __name__ == "__main__":
    main()
