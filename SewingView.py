"""Small, FreeCAD-independent helpers for Sewing workbench views."""


def pattern_pieces_for_2d(objects):
    """Return pattern pieces participating in the sewing 2D focus.

    The sewing view is a presentation of the authoritative pattern geometry,
    so PatternPiece objects are included alongside seam/network overlays.
    Preserve document order to keep selection deterministic.
    """
    return [
        obj for obj in objects
        if getattr(obj, "PatternType", "") == "PatternPiece"
    ]
