"""Small generated, license-safe garment fixtures for regression tests."""
from freecad_cloth.pattern.PatternGeometry import rectangle

def two_piece_rectangle():
    return {"pieces": [rectangle(100, 60), rectangle(100, 60)], "seams": [("right", "left")]}

def curved_panel():
    return {"pieces": [rectangle(100, 60)], "curved": True}

def mirrored_pair():
    return {"pieces": [rectangle(80, 50), rectangle(80, 50)], "mirrored": True}

def multi_piece():
    return {"pieces": [rectangle(60, 40), rectangle(70, 50), rectangle(50, 35)], "seams": 3}
