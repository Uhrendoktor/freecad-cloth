from __future__ import annotations

import binascii
import struct
import zlib
from pathlib import Path

import pytest

from freecad_cloth.common.VisualCaptureValidation import (
    png_has_visible_content,
    validate_png_capture,
)


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", binascii.crc32(kind + payload) & 0xFFFFFFFF)
    )


def _write_png(path: Path, width: int, height: int, pixels: list[tuple[int, int, int]]) -> None:
    rows = []
    for row_start in range(0, len(pixels), width):
        row = pixels[row_start : row_start + width]
        rows.append(b"\x00" + b"".join(bytes(rgb) for rgb in row))
    payload = zlib.compress(b"".join(rows))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", payload)
        + _chunk(b"IEND", b"")
    )


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
    assert metrics["opaque_pixels"] == 9
    assert metrics["nonwhite_pixels"] == 3
    assert metrics["distinct_rgb"] == 4


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
    rows = []
    width = height = 3
    for _ in range(height):
        rows.append(b"\x00" + b"".join(bytes((0, 0, 0, 0)) for _ in range(width)))
    payload = zlib.compress(b"".join(rows))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", payload)
        + _chunk(b"IEND", b"")
    )
    with pytest.raises(ValueError, match="effectively transparent"):
        validate_png_capture(path, expected_width=3, expected_height=3)


def test_validate_png_capture_rejects_wrong_dimensions(tmp_path: Path):
    path = tmp_path / "wrong-size.png"
    _write_png(path, 3, 3, [(0, 0, 0)] * 9)
    with pytest.raises(ValueError, match="dimensions"):
        validate_png_capture(path, expected_width=4, expected_height=3)


def test_png_visible_content_reuses_crc_checked_parser_and_capture_thresholds(tmp_path: Path):
    path = tmp_path / "colored.png"
    _write_png(path, 2, 2, [(255, 0, 0), (255, 255, 255), (255, 255, 255), (255, 255, 255)])
    assert png_has_visible_content(
        path,
        expected_width=2,
        expected_height=2,
        minimum_pixels=1,
        channel_threshold=250,
    )
    assert not png_has_visible_content(
        path,
        expected_width=2,
        expected_height=2,
        minimum_pixels=1,
        channel_threshold=245,
        require_all_channels_below_threshold=True,
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
