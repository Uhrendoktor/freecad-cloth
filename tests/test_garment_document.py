from freecad_cloth.common.GarmentDocument import garment_domain


def test_garment_domain_classifies_authoritative_objects():
    assert garment_domain(type("O", (), {"PatternType": "PatternPiece", "Name": "Front"})()) == "Patterns"
    assert garment_domain(type("O", (), {"SeamId": "seam-1", "Name": "Seam"})()) == "Sewing"
    assert garment_domain(type("O", (), {"SewingType": "SewingNetwork", "Name": "SewingNetwork"})()) == "Sewing"
    assert garment_domain(type("O", (), {"AvatarType": "ClothAvatar", "Name": "ClothAvatar"})()) == "Avatar"
    assert garment_domain(type("O", (), {"Name": "DrapeTarget", "TargetType": "Mannequin"})()) == "Fitting"
    assert garment_domain(type("O", (), {"Name": "ClothSimulation", "Proxy": type("P", (), {"Type": "ClothSimulation"})()})()) == "Simulation"


def test_garment_domain_ignores_unrelated_document_objects():
    assert garment_domain(type("O", (), {"Name": "RandomPart"})()) is None
