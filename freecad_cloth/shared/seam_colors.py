"""Neutral deterministic seam presentation helpers."""

from colorsys import hsv_to_rgb
from hashlib import sha512

_SEAM_COLOR_SATURATION = 0.78
_SEAM_COLOR_VALUE = 0.92
_SEAM_COLOR_HASH_SCALE = float(1 << 64)


def _seam_color_for_id(seam_id):
    """Return a stable presentation color derived only from semantic seam identity."""
    identity = str(seam_id).strip()
    if not identity:
        raise ValueError("seam identity must not be empty")
    digest = sha512(identity.encode("utf-8")).digest()
    hue = int.from_bytes(digest[44:52], "big") / _SEAM_COLOR_HASH_SCALE
    rgb = hsv_to_rgb(hue, _SEAM_COLOR_SATURATION, _SEAM_COLOR_VALUE)
    return tuple(round(channel, 6) for channel in rgb)


def seam_color_map(seam_ids):
    """Return deterministic seam colors keyed only by semantic seam ID."""
    ids = sorted({str(seam_id).strip() for seam_id in seam_ids if str(seam_id).strip()})
    return {seam_id: _seam_color_for_id(seam_id) for seam_id in ids}


def apply_seam_colors(objects):
    """Apply deterministic colors to document seam objects."""
    seam_objects = [obj for obj in objects if str(getattr(obj, "SeamId", "")).strip()]
    colors = seam_color_map(getattr(obj, "SeamId", "") for obj in seam_objects)
    for obj in seam_objects:
        view = getattr(obj, "ViewObject", None)
        color = colors.get(str(getattr(obj, "SeamId", "")))
        if view is not None and color is not None:
            view.LineColor = color
    return colors
