# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression and property tests for visual-capture validation."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from PIL import Image
from pydantic import ValidationError

from freecad_cloth.common.ValidationModels import PngCaptureMetrics
from freecad_cloth.common.VisualCaptureValidation import (
    png_has_visible_content,
    validate_png_capture,
)
from tests.support.assertions import require as _require


def _write_png(
    path: Path,
    width: int,
    height: int,
    pixels: list[tuple[int, ...]],
    *,
    mode: str = "RGB",
) -> None:
    """Write test pixels to a PNG image using Pillow's production encoder.

    Args:
        path: Destination path where the generated PNG should be saved.
        width: Horizontal pixel count for the image canvas.
        height: Vertical pixel count for the image canvas.
        pixels: Ordered pixel channel values supplied to the image encoder.
        mode: Pillow image mode defining each pixel's channel layout.
    """
    image = Image.new(mode, (width, height))
    image.putdata(pixels)
    image.save(path, format="PNG")


def test_validate_png_capture_accepts_real_nonuniform_rgb(tmp_path: Path) -> None:
    """Accept a colorful RGB capture with enough visible, opaque pixels.

    Args:
        tmp_path: Temporary directory supplied by pytest for generated assets.
    """
    path = tmp_path / "capture.png"
    pixels = [(255, 255, 255)] * 9
    pixels[0] = (10, 20, 30)
    pixels[4] = (80, 90, 100)
    pixels[8] = (160, 170, 180)
    _write_png(path, 3, 3, pixels)
    metrics = validate_png_capture(
        path,
        expected_width=3,
        expected_height=3,
        min_nonwhite_pixels=2,
        min_distinct_rgb=3,
        min_opaque_pixels=9,
    )
    _require(
        condition=metrics
        == {
            "width": 3,
            "height": 3,
            "opaque_pixels": 9,
            "nonwhite_pixels": 3,
            "distinct_rgb": 4,
        },
        message="validated PNG metrics should reflect the generated RGB image",
    )


def test_validate_png_capture_rejects_uniform_capture(tmp_path: Path) -> None:
    """Reject an all-white image that contains no visible scene content.

    Args:
        tmp_path: Temporary directory supplied by pytest for generated assets.
    """
    path = tmp_path / "uniform.png"
    _write_png(path, 3, 3, [(255, 255, 255)] * 9)
    with pytest.raises(ValueError, match="effectively blank"):
        validate_png_capture(path, expected_width=3, expected_height=3, min_opaque_pixels=9)


def test_validate_png_capture_rejects_all_black_capture(tmp_path: Path) -> None:
    """Reject a uniformly black image rather than treating it as valid evidence.

    Args:
        tmp_path: Temporary directory supplied by pytest for generated assets.
    """
    path = tmp_path / "black.png"
    _write_png(path, 3, 3, [(0, 0, 0)] * 9)
    with pytest.raises(ValueError, match="effectively uniform"):
        validate_png_capture(
            path,
            expected_width=3,
            expected_height=3,
            min_nonwhite_pixels=1,
            min_opaque_pixels=9,
        )


def test_validate_png_capture_rejects_transparent_capture(tmp_path: Path) -> None:
    """Reject a fully transparent RGBA image as unusable visual evidence.

    Args:
        tmp_path: Temporary directory supplied by pytest for generated assets.
    """
    path = tmp_path / "transparent.png"
    _write_png(path, 3, 3, [(0, 0, 0, 0)] * 9, mode="RGBA")
    with pytest.raises(ValueError, match="effectively transparent"):
        validate_png_capture(path, expected_width=3, expected_height=3)


def test_png_has_visible_content_supports_threshold_semantics(tmp_path: Path) -> None:
    """Apply the selected per-channel visibility threshold consistently.

    Args:
        tmp_path: Temporary directory supplied by pytest for generated assets.
    """
    path = tmp_path / "colored.png"
    pixels = [(255, 255, 255)] * 9
    pixels[0] = (10, 255, 255)
    _write_png(path, 3, 3, pixels)
    _require(
        condition=png_has_visible_content(
            path,
            minimum_pixels=1,
            expected_width=3,
            expected_height=3,
            pixel_threshold=245,
        ),
        message="a pixel with one channel below the threshold should count as visible",
    )
    _require(
        condition=not png_has_visible_content(
            path,
            minimum_pixels=1,
            expected_width=3,
            expected_height=3,
            pixel_threshold=245,
            require_all_channels_below=True,
        ),
        message="requiring all channels below the threshold should exclude this pixel",
    )


def test_png_has_visible_content_rejects_malformed_input(tmp_path: Path) -> None:
    """Return false when the supplied file cannot be decoded as a PNG.

    Args:
        tmp_path: Temporary directory supplied by pytest for generated assets.
    """
    path = tmp_path / "corrupt.png"
    path.write_bytes(b"not a PNG")
    _require(
        condition=not png_has_visible_content(path, minimum_pixels=1),
        message="malformed PNG bytes must not be reported as visible content",
    )


def test_validate_png_capture_rejects_wrong_dimensions(tmp_path: Path) -> None:
    """Reject capture dimensions that differ from the expected viewport size.

    Args:
        tmp_path: Temporary directory supplied by pytest for generated assets.
    """
    path = tmp_path / "wrong-size.png"
    _write_png(path, 3, 3, [(0, 0, 0)] * 9)
    with pytest.raises(ValueError, match="dimensions"):
        validate_png_capture(path, expected_width=4, expected_height=3)


def test_png_capture_options_reject_non_integer_or_out_of_range_policy() -> None:
    """Reject boolean and out-of-range values for numeric capture policies."""
    with pytest.raises(ValidationError, match="pixel_threshold"):
        png_has_visible_content("unused.png", pixel_threshold=True)
    with pytest.raises(ValidationError, match="pixel_threshold"):
        png_has_visible_content("unused.png", pixel_threshold=257)


def test_png_metrics_reject_impossible_pixel_counts() -> None:
    """Reject image metrics whose opaque pixel count exceeds the image area."""
    with pytest.raises(ValidationError, match="opaque pixel count"):
        PngCaptureMetrics(
            width=1,
            height=1,
            opaque_pixels=2,
            nonwhite_pixels=1,
            distinct_rgb=1,
        )


@settings(max_examples=40, deadline=None)
@given(
    pixels=st.lists(
        st.tuples(
            st.integers(min_value=0, max_value=255),
            st.integers(min_value=0, max_value=255),
            st.integers(min_value=0, max_value=255),
        ),
        min_size=16,
        max_size=16,
    ),
    threshold=st.integers(min_value=0, max_value=256),
    minimum=st.integers(min_value=0, max_value=16),
)
def test_visible_pixel_count_matches_decoded_rgb_predicate(
    pixels: list[tuple[int, int, int]],
    threshold: int,
    minimum: int,
) -> None:
    """Property-test the Pillow decode and vectorized visibility predicate.

    Args:
        pixels: RGB tuples generated for a synthetic sixteen-pixel image.
        threshold: Per-channel cutoff used to classify pixels as visible.
        minimum: Minimum visible-pixel count required by the validation policy.
    """
    with TemporaryDirectory() as directory:
        path = Path(directory) / "generated.png"
        _write_png(path, 4, 4, pixels)
        expected = sum(1 for rgb in pixels if any(channel < threshold for channel in rgb))
        _require(
            condition=png_has_visible_content(
                path,
                minimum_pixels=minimum,
                expected_width=4,
                expected_height=4,
                pixel_threshold=threshold,
            )
            is (expected >= minimum),
            message="visible-content evaluation should match the decoded RGB predicate",
        )


def test_png_visible_content_reuses_crc_checked_parser_and_capture_thresholds(
    tmp_path: Path,
) -> None:
    """Reuse capture thresholds when deciding whether a parsed PNG is visible.

    Args:
        tmp_path: Temporary directory supplied by pytest for generated assets.
    """
    path = tmp_path / "colored.png"
    _write_png(
        path,
        2,
        2,
        [(255, 0, 0), (255, 255, 255), (255, 255, 255), (255, 255, 255)],
    )
    _require(
        condition=png_has_visible_content(
            path,
            expected_width=2,
            expected_height=2,
            minimum_pixels=1,
            pixel_threshold=250,
        ),
        message="a visible red pixel should satisfy the selected threshold",
    )
    _require(
        condition=not png_has_visible_content(
            path,
            expected_width=2,
            expected_height=2,
            minimum_pixels=1,
            pixel_threshold=245,
            require_all_channels_below=True,
        ),
        message="all-channel thresholding should reject the single red pixel",
    )
    _require(
        condition=not png_has_visible_content(path, expected_width=3, expected_height=2),
        message="visibility checks should reject a mismatch in expected dimensions",
    )


def test_png_visible_content_rejects_bad_crc_and_uniform_white(tmp_path: Path) -> None:
    """Reject uniform images and PNG data whose checksum validation fails.

    Args:
        tmp_path: Temporary directory supplied by pytest for generated assets.
    """
    path = tmp_path / "white.png"
    _write_png(path, 2, 2, [(255, 255, 255)] * 4)
    _require(
        condition=not png_has_visible_content(path, minimum_pixels=1),
        message="uniform white images should not count as visible content",
    )
    data = bytearray(path.read_bytes())
    data[-13] ^= 1
    corrupt_path = tmp_path / "corrupt.png"
    corrupt_path.write_bytes(data)
    _require(
        condition=not png_has_visible_content(corrupt_path, minimum_pixels=1),
        message="invalid PNG checksums should cause visibility validation to fail",
    )
