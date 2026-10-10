"""Neutral deterministic seam presentation helpers."""

from collections.abc import Callable, Iterable
from colorsys import hsv_to_rgb
from hashlib import sha512

_SEAM_COLOR_SATURATION = 0.78
_SEAM_COLOR_VALUE = 0.92
_SEAM_COLOR_HASH_SCALE = float(1 << 64)
_NEUTRAL_SEAM_COLOR = (0.48, 0.48, 0.48)
_SEAM_COLOR_HIGHLIGHTS_ENABLED = True
_SEAM_REFRESH_CALLBACK: Callable[[object | None], None] | None = None


def register_seam_refresh_callback(
    callback: Callable[[object | None], None] | None,
) -> None:
    """Register an optional GUI-layer refresh without reversing module dependencies."""
    global _SEAM_REFRESH_CALLBACK
    _SEAM_REFRESH_CALLBACK = callback


def set_seam_color_highlighting_enabled(enabled: bool) -> None:
    """Choose identity colors or neutral linework for native seam view objects."""
    global _SEAM_COLOR_HIGHLIGHTS_ENABLED
    _SEAM_COLOR_HIGHLIGHTS_ENABLED = bool(enabled)


def seam_color_highlighting_enabled() -> bool:
    """Return whether native seam objects should use identity-specific colors."""
    return _SEAM_COLOR_HIGHLIGHTS_ENABLED


def _seam_color_for_id(seam_id: object) -> tuple[float, float, float]:
    """Return a stable presentation color derived only from semantic seam identity."""
    identity = str(seam_id).strip()
    if not identity:
        raise ValueError("seam identity must not be empty")
    digest = sha512(identity.encode("utf-8")).digest()
    hue = int.from_bytes(digest[44:52], "big") / _SEAM_COLOR_HASH_SCALE
    red, green, blue = hsv_to_rgb(hue, _SEAM_COLOR_SATURATION, _SEAM_COLOR_VALUE)
    return round(red, 6), round(green, 6), round(blue, 6)


def seam_color_map(seam_ids: Iterable[object]) -> dict[str, tuple[float, float, float]]:
    """Return deterministic seam colors keyed only by non-empty semantic IDs."""
    identities = [str(seam_id).strip() for seam_id in seam_ids]
    if any(not identity for identity in identities):
        raise ValueError("seam identity must not be empty")
    ids = sorted(set(identities))
    return {seam_id: _seam_color_for_id(seam_id) for seam_id in ids}


def apply_seam_colors(objects: Iterable[object]) -> dict[str, tuple[float, float, float]]:
    """Apply deterministic colors to document seam objects."""
    seam_objects = [obj for obj in objects if str(getattr(obj, "SeamId", "")).strip()]
    colors = seam_color_map(getattr(obj, "SeamId", "") for obj in seam_objects)
    for obj in seam_objects:
        view = getattr(obj, "ViewObject", None)
        color = colors.get(str(getattr(obj, "SeamId", "")))
        if view is not None and color is not None:
            view.LineColor = color if _SEAM_COLOR_HIGHLIGHTS_ENABLED else _NEUTRAL_SEAM_COLOR
    if seam_objects and _SEAM_REFRESH_CALLBACK is not None:
        document = getattr(seam_objects[0], "Document", None)
        if document is not None:
            _SEAM_REFRESH_CALLBACK(document)
    return colors
