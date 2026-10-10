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


def _write_png(
    path: Path,
    width: int,
    height: int,
    pixels: list[tuple[int, ...]],
    *,
    mode: str = "RGB",
) -> None:
    """Write test pixels through Pillow rather than duplicating PNG encoding."""
    image = Image.new(mode, (width, height))
    image.putdata(pixels)
    image.save(path, format="PNG")


def test_validate_png_capture_accepts_real_nonuniform_rgb(tmp_path: Path):
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
    assert metrics == {
        "width": 3,
        "height": 3,
        "opaque_pixels": 9,
        "nonwhite_pixels": 3,
        "distinct_rgb": 4,
    }


def test_validate_png_capture_rejects_uniform_capture(tmp_path: Path):
    path = tmp_path / "uniform.png"
    _write_png(path, 3, 3, [(255, 255, 255)] * 9)
    with pytest.raises(ValueError, match="effectively blank"):
        validate_png_capture(path, expected_width=3, expected_height=3, min_opaque_pixels=9)


def test_validate_png_capture_rejects_all_black_capture(tmp_path: Path):
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


def test_validate_png_capture_rejects_transparent_capture(tmp_path: Path):
    path = tmp_path / "transparent.png"
    _write_png(path, 3, 3, [(0, 0, 0, 0)] * 9, mode="RGBA")
    with pytest.raises(ValueError, match="effectively transparent"):
        validate_png_capture(path, expected_width=3, expected_height=3)


def test_png_has_visible_content_supports_threshold_semantics(tmp_path: Path):
    path = tmp_path / "colored.png"
    pixels = [(255, 255, 255)] * 9
    pixels[0] = (10, 255, 255)
    _write_png(path, 3, 3, pixels)
    assert png_has_visible_content(
        path,
        minimum_pixels=1,
        expected_width=3,
        expected_height=3,
        pixel_threshold=245,
    )
    assert not png_has_visible_content(
        path,
        minimum_pixels=1,
        expected_width=3,
        expected_height=3,
        pixel_threshold=245,
        require_all_channels_below=True,
    )


def test_png_has_visible_content_rejects_malformed_input(tmp_path: Path):
    path = tmp_path / "corrupt.png"
    path.write_bytes(b"not a PNG")
    assert not png_has_visible_content(path, minimum_pixels=1)


def test_validate_png_capture_rejects_wrong_dimensions(tmp_path: Path):
    path = tmp_path / "wrong-size.png"
    _write_png(path, 3, 3, [(0, 0, 0)] * 9)
    with pytest.raises(ValueError, match="dimensions"):
        validate_png_capture(path, expected_width=4, expected_height=3)


def test_png_capture_options_reject_non_integer_or_out_of_range_policy():
    with pytest.raises(ValidationError):
        png_has_visible_content("unused.png", pixel_threshold=True)
    with pytest.raises(ValidationError):
        png_has_visible_content("unused.png", pixel_threshold=257)


def test_png_metrics_reject_impossible_pixel_counts():
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
):
    """Property-test the Pillow decode and vectorized visibility predicate."""
    with TemporaryDirectory() as directory:
        path = Path(directory) / "generated.png"
        _write_png(path, 4, 4, pixels)
        expected = sum(1 for rgb in pixels if any(channel < threshold for channel in rgb))
        assert png_has_visible_content(
            path,
            minimum_pixels=minimum,
            expected_width=4,
            expected_height=4,
            pixel_threshold=threshold,
        ) is (expected >= minimum)


def test_png_visible_content_reuses_crc_checked_parser_and_capture_thresholds(tmp_path: Path):
    path = tmp_path / "colored.png"
    _write_png(
        path,
        2,
        2,
        [(255, 0, 0), (255, 255, 255), (255, 255, 255), (255, 255, 255)],
    )
    assert png_has_visible_content(
        path,
        expected_width=2,
        expected_height=2,
        minimum_pixels=1,
        pixel_threshold=250,
    )
    assert not png_has_visible_content(
        path,
        expected_width=2,
        expected_height=2,
        minimum_pixels=1,
        pixel_threshold=245,
        require_all_channels_below=True,
    )
    assert not png_has_visible_content(path, expected_width=3, expected_height=2)


def test_png_visible_content_rejects_bad_crc_and_uniform_white(tmp_path: Path):
    path = tmp_path / "white.png"
    _write_png(path, 2, 2, [(255, 255, 255)] * 4)
    assert not png_has_visible_content(path, minimum_pixels=1)
    data = bytearray(path.read_bytes())
    data[-13] ^= 1
    corrupt_path = tmp_path / "corrupt.png"
    corrupt_path.write_bytes(data)
    assert not png_has_visible_content(corrupt_path, minimum_pixels=1)
