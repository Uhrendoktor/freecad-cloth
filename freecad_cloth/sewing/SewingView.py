"""Small, FreeCAD-independent helpers for Sewing workbench views."""
from colorsys import hsv_to_rgb


_SEAM_GOLDEN_ANGLE = 0.618033988749895


def seam_color_map(seam_ids):
    """Return deterministic, visually distinct colors keyed by seam id."""
    ids = sorted({str(seam_id) for seam_id in seam_ids if str(seam_id).strip()})
    result = {}
    for index, seam_id in enumerate(ids):
        hue = (index * _SEAM_GOLDEN_ANGLE) % 1.0
        rgb = hsv_to_rgb(hue, 0.78, 0.92)
        result[seam_id] = tuple(round(channel, 6) for channel in rgb)
    return result


def apply_seam_colors(objects):
    """Apply one deterministic line color to each canonical seam object."""
    seam_objects = [
        obj for obj in objects
        if str(getattr(obj, "SeamId", "")).strip()
    ]
    colors = seam_color_map(getattr(obj, "SeamId", "") for obj in seam_objects)
    for obj in seam_objects:
        view = getattr(obj, "ViewObject", None)
        color = colors.get(str(getattr(obj, "SeamId", "")))
        if view is not None and color is not None:
            view.LineColor = color
    return colors


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
