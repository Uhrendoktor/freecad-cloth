"""Small generated, license-safe garment fixtures for regression tests."""

from freecad_cloth.pattern.PatternGeometry import rectangle


def two_piece_rectangle() -> dict[str, object]:
    """Create two equal rectangular panels joined along opposing side edges.

    Returns:
        Fixture payload containing two 100-by-60 panels and one right-to-left seam.
    """
    return {"pieces": [rectangle(100, 60), rectangle(100, 60)], "seams": [("right", "left")]}


def curved_panel() -> dict[str, object]:
    """Create one rectangular panel fixture marked for curved-boundary tests.

    Returns:
        Fixture payload containing one panel and a flag enabling curved-panel cases.
    """
    return {"pieces": [rectangle(100, 60)], "curved": True}


def mirrored_pair() -> dict[str, object]:
    """Create two equal panels for mirrored-pair arrangement tests.

    Returns:
        Fixture payload containing two 80-by-50 panels and a mirrored flag.
    """
    return {"pieces": [rectangle(80, 50), rectangle(80, 50)], "mirrored": True}


def multi_piece() -> dict[str, object]:
    """Create a three-panel fixture for multi-piece assembly tests.

    Returns:
        Fixture payload containing three panels with varied dimensions and three seams.
    """
    return {"pieces": [rectangle(60, 40), rectangle(70, 50), rectangle(50, 35)], "seams": 3}
