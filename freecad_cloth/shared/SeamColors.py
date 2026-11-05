# Copyright (C) 2026 FreeCAD Cloth contributors
"""Neutral deterministic seam presentation helpers."""

from collections.abc import Callable, Iterable
from colorsys import hsv_to_rgb
from hashlib import sha512

from pydantic.dataclasses import dataclass

_SEAM_COLOR_SATURATION = 0.78
_SEAM_COLOR_VALUE = 0.92
_SEAM_COLOR_HASH_SCALE = float(1 << 64)
_NEUTRAL_SEAM_COLOR = (0.48, 0.48, 0.48)


@dataclass
class _SeamColorState:
    """Mutable display configuration shared by seam-color operations."""

    highlights_enabled: bool = True
    refresh_callback: Callable[[object | None], None] | None = None


_SEAM_COLOR_STATE = _SeamColorState()


def register_seam_refresh_callback(
    callback: Callable[[object | None], None] | None,
) -> None:
    """Register an optional GUI-layer refresh without reversing module dependencies.

    Args:
        callback: Optional document-refresh callback; None clears a prior callback.
    """
    _SEAM_COLOR_STATE.refresh_callback = callback


def set_seam_color_highlighting_enabled(enabled: object) -> None:
    """Choose identity colors or neutral linework for native seam view objects.

    Args:
        enabled: Value converted to a boolean to select semantic or neutral colors.
    """
    _SEAM_COLOR_STATE.highlights_enabled = bool(enabled)


def seam_color_highlighting_enabled() -> bool:
    """Return whether native seam objects should use identity-specific colors.

    Returns:
        bool: Whether identity-specific colors are enabled.
    """
    return _SEAM_COLOR_STATE.highlights_enabled


def _seam_color_for_id(seam_id: object) -> tuple[float, float, float]:
    """Return a stable presentation color derived only from semantic seam identity.

    Args:
        seam_id: Semantic seam identifier used as the deterministic color seed.

    Returns:
        tuple[float, float, float]: RGB color with channels rounded to six decimals.

    Raises:
        ValueError: If the supplied identity is empty after trimming whitespace.
    """
    identity = str(seam_id).strip()
    if not identity:
        msg = "seam identity must not be empty"
        raise ValueError(msg)
    digest = sha512(identity.encode("utf-8")).digest()
    hue = int.from_bytes(digest[44:52], "big") / _SEAM_COLOR_HASH_SCALE
    rgb = hsv_to_rgb(hue, _SEAM_COLOR_SATURATION, _SEAM_COLOR_VALUE)
    return round(rgb[0], 6), round(rgb[1], 6), round(rgb[2], 6)


def seam_color_map(seam_ids: Iterable[object]) -> dict[str, tuple[float, float, float]]:
    """Return deterministic seam colors keyed only by non-empty semantic IDs.

    Args:
        seam_ids: Iterable of semantic seam identifiers.

    Returns:
        dict[str, tuple[float, float, float]]: Identity-to-RGB mappings in sorted key order.

    Raises:
        ValueError: If any supplied identity is empty after trimming whitespace.
    """
    identities = [str(seam_id).strip() for seam_id in seam_ids]
    if any(not identity for identity in identities):
        msg = "seam identity must not be empty"
        raise ValueError(msg)
    ids = sorted(set(identities))
    return {seam_id: _seam_color_for_id(seam_id) for seam_id in ids}


def apply_seam_colors(objects: Iterable[object]) -> dict[str, tuple[float, float, float]]:
    """Apply deterministic colors to document seam objects.

    Args:
        objects: Document objects with optional semantic SeamId and ViewObject fields.

    Returns:
        dict[str, tuple[float, float, float]]: Applied RGB colors keyed by seam identity.
    """
    seam_objects = [obj for obj in objects if str(getattr(obj, "SeamId", "")).strip()]
    colors = seam_color_map(getattr(obj, "SeamId", "") for obj in seam_objects)
    for obj in seam_objects:
        view = getattr(obj, "ViewObject", None)
        color = colors.get(str(getattr(obj, "SeamId", "")))
        if view is not None and color is not None:
            view.LineColor = color if _SEAM_COLOR_STATE.highlights_enabled else _NEUTRAL_SEAM_COLOR
    refresh_callback = _SEAM_COLOR_STATE.refresh_callback
    if seam_objects and refresh_callback is not None:
        document = getattr(seam_objects[0], "Document", None)
        if document is not None:
            refresh_callback(document)
    return colors
