"""Pillow- and Pydantic-backed validation for FreeCAD screenshot captures."""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
from PIL import Image

from freecad_cloth.common.ValidationModels import PngCaptureMetrics, PngCaptureOptions


def _capture_metrics(
    path: Path | str,
    options: PngCaptureOptions,
    *,
    track_colors: bool = True,
) -> PngCaptureMetrics:
    """Decode a PNG using Pillow and validate pixel statistics with Pydantic."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        try:
            with Image.open(path) as probe:
                if probe.format != "PNG":
                    raise ValueError("invalid PNG signature")
                width, height = probe.size
                if (
                    options.expected_width is not None
                    and options.expected_height is not None
                    and (width, height) != (options.expected_width, options.expected_height)
                ):
                    raise ValueError(
                        "PNG dimensions are %dx%d, expected %dx%d"
                        % (width, height, options.expected_width, options.expected_height)
                    )
                if options.expected_width is not None and width != options.expected_width:
                    raise ValueError(f"PNG width is {width}, expected {options.expected_width}")
                if options.expected_height is not None and height != options.expected_height:
                    raise ValueError(f"PNG height is {height}, expected {options.expected_height}")
                probe.verify()

            # Pillow must reopen the image after verify(); load() detects truncated pixel data.
            with Image.open(path) as image:
                if image.format != "PNG":
                    raise ValueError("invalid PNG signature")
                image.load()
                pixels = np.array(image.convert("RGBA"), dtype=np.uint8, copy=True)
        except (
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
            OSError,
            SyntaxError,
        ) as exc:
            raise ValueError("invalid or unreadable PNG capture") from exc

    rgb = pixels[..., :3]
    opaque = pixels[..., 3] > 8
    if options.require_all_channels_below:
        visible = np.all(rgb < options.pixel_threshold, axis=2)
    else:
        visible = np.any(rgb < options.pixel_threshold, axis=2)

    opaque_pixels = int(np.count_nonzero(opaque))
    nonwhite_pixels = int(np.count_nonzero(opaque & visible))
    distinct_rgb = 0
    if track_colors and opaque_pixels:
        opaque_colors = rgb[opaque].reshape((-1, 3))
        distinct_rgb = int(np.unique(opaque_colors, axis=0).shape[0])

    return PngCaptureMetrics(
        width=int(pixels.shape[1]),
        height=int(pixels.shape[0]),
        opaque_pixels=opaque_pixels,
        nonwhite_pixels=nonwhite_pixels,
        distinct_rgb=distinct_rgb,
    )


def png_has_visible_content(
    path: Path | str,
    *,
    minimum_pixels: int = 64,
    expected_width: int | None = None,
    expected_height: int | None = None,
    pixel_threshold: int = 250,
    require_all_channels_below: bool = False,
) -> bool:
    """Return whether a valid PNG contains enough non-background opaque pixels.

    Unsupported, truncated, or incorrectly sized captures return False so GUI retry
    loops can reject the frame without duplicating image decoding code. Invalid options
    raise Pydantic ValidationError instead of being mistaken for a bad captured frame.
    """
    options = PngCaptureOptions(
        expected_width=expected_width,
        expected_height=expected_height,
        minimum_pixels=minimum_pixels,
        pixel_threshold=pixel_threshold,
        require_all_channels_below=require_all_channels_below,
    )
    try:
        metrics = _capture_metrics(path, options, track_colors=False)
    except (OSError, ValueError, OverflowError):
        return False
    return metrics.nonwhite_pixels >= options.minimum_pixels


def png_has_visible_content(
    path: Path,
    *,
    minimum_pixels: int = 64,
    channel_threshold: int = 250,
    require_all_channels_below_threshold: bool = False,
    expected_width: int | None = None,
    expected_height: int | None = None,
) -> bool:
    """Return whether a PNG contains enough visible non-background pixels.

    The helper shares the CRC-checked parser and PNG filter support with
    validate_png_capture. Malformed or unsupported captures return False.
    """
    if minimum_pixels < 1:
        raise ValueError("minimum_pixels must be positive")
    if not 0 <= channel_threshold <= 256:
        raise ValueError("channel_threshold must be in [0, 256]")
    if (expected_width is None) != (expected_height is None):
        raise ValueError("expected_width and expected_height must be supplied together")

    try:
        width, height, raw, bytes_per_pixel = _parse_png(Path(path))
        if expected_width is not None and (width, height) != (expected_width, expected_height):
            return False
        visible = 0
        for row in _unfilter_rows(raw, width, height, bytes_per_pixel):
            for index in range(0, len(row), bytes_per_pixel):
                if bytes_per_pixel == 4 and row[index + 3] <= 8:
                    continue
                rgb = row[index : index + 3]
                is_visible = (
                    all(value < channel_threshold for value in rgb)
                    if require_all_channels_below_threshold
                    else any(value < channel_threshold for value in rgb)
                )
                if is_visible:
                    visible += 1
                    if visible >= minimum_pixels:
                        return True
        return False
    except (OSError, ValueError, struct.error, zlib.error):
        return False


def validate_png_capture(
    path: Path | str,
    *,
    expected_width: int,
    expected_height: int,
    min_nonwhite_pixels: int = 64,
    min_distinct_rgb: int = 8,
    min_opaque_pixels: int = 64,
) -> dict[str, int]:
    """Reject unreadable, transparent, blank, or effectively uniform PNG captures."""
    options = PngCaptureOptions(
        expected_width=expected_width,
        expected_height=expected_height,
        minimum_pixels=min_nonwhite_pixels,
        min_opaque_pixels=min_opaque_pixels,
        min_distinct_rgb=min_distinct_rgb,
    )
    metrics = _capture_metrics(path, options)
    if metrics.opaque_pixels < options.min_opaque_pixels:
        raise ValueError(
            "PNG content is effectively transparent: opaque_pixels=%d minimum=%d"
            % (metrics.opaque_pixels, options.min_opaque_pixels)
        )
    if metrics.nonwhite_pixels < options.minimum_pixels:
        raise ValueError(
            "PNG content is effectively blank: nonwhite_pixels=%d minimum=%d"
            % (metrics.nonwhite_pixels, options.minimum_pixels)
        )
    if metrics.distinct_rgb < options.min_distinct_rgb:
        raise ValueError(
            "PNG content is effectively uniform: distinct_rgb=%d minimum=%d"
            % (metrics.distinct_rgb, options.min_distinct_rgb)
        )
    return metrics.model_dump()
