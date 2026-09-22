"""Pure/document-level contract tests for the native garment hierarchy."""

from types import SimpleNamespace

from freecad_cloth.common.GarmentDocument import classify_members, classify_object


def obj(name, **props):
    return SimpleNamespace(Name=name, Label=name, **props)


def test_garment_roles_classify_existing_authoritative_objects():
    front = obj("Front", PatternType="PatternPiece")
    seam = obj("Seam", SeamId="side")
    network = obj("SewingNetwork", SewingType="SewingNetwork")
    fitting = obj("FittingScene", FittingType="FittingScene")
    point = obj("ArrangementPoint_waist", FittingType="ArrangementPoint")
    avatar = obj("ClothAvatar", AvatarType="ClothAvatar")
    target = obj("DrapeTarget")
    simulation = obj("ClothSimulation", Proxy=SimpleNamespace(Type="ClothSimulation"))

    assert classify_object(front) == "pattern"
    assert classify_object(seam) == "sewing"
    assert classify_object(network) == "sewing"
    assert classify_object(fitting) == "fitting"
    assert classify_object(point) == "fitting"
    assert classify_object(avatar) == "avatar"
    assert classify_object(target) == "simulation"
    assert classify_object(simulation) == "simulation"


def test_garment_members_are_deterministic_and_do_not_duplicate_objects():
    front = obj("Front", PatternType="PatternPiece")
    back = obj("Back", PatternType="PatternPiece")
    seam = obj("Seam", SeamId="side")
    ignored = obj("RandomObject")

    members = classify_members((back, seam, front, ignored, front))
    assert [item.Name for item in members["pattern"]] == ["Back", "Front"]
    assert [item.Name for item in members["sewing"]] == ["Seam"]
    assert all(item.Name != "RandomObject" for items in members.values() for item in items)
