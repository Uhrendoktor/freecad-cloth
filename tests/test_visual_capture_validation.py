from __future__ import annotations

import binascii
import struct
import zlib
from pathlib import Path

import pytest

from freecad_cloth.common.VisualCaptureValidation import validate_png_capture


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", binascii.crc32(kind + payload) & 0xFFFFFFFF)


def _write_png(path: Path, width: int, height: int, pixels: list[tuple[int, int, int]]) -> None:
    rows = []
    for row_start in range(0, len(pixels), width):
        row = pixels[row_start : row_start + width]
        rows.append(b"\\x00" + b"".join(bytes(rgb) for rgb in row))
    payload = zlib.compress(b"".join(rows))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(b"\\x89PNG\\r\\n\\x1a\\n" + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", payload) + _chunk(b"IEND", b""))


def test_validate_png_capture_accepts_real_nonuniform_rgb(tmp_path: Path):
    path = tmp_path / "capture.png"
    pixels = [(255, 255, 255)] * 9
    pixels[0] = (10, 20, 30)
    pixels[4] = (80, 90, 100)
    pixels[8] = (160, 170, 180)
    _write_png(path, 3, 3, pixels)
    metrics = validate_png_capture(path, expected_width=3, expected_height=3, min_nonwhite_pixels=2, min_distinct_rgb=3)
    assert metrics["nonwhite_pixels"] == 3
    assert metrics["distinct_rgb"] == 4


def test_validate_png_capture_rejects_uniform_capture(tmp_path: Path):
    path = tmp_path / "uniform.png"
    _write_png(path, 3, 3, [(255, 255, 255)] * 9)
    with pytest.raises(ValueError, match="effectively blank"):
        validate_png_capture(path, expected_width=3, expected_height=3)


def test_validate_png_capture_rejects_wrong_dimensions(tmp_path: Path):
    path = tmp_path / "wrong-size.png"
    _write_png(path, 3, 3, [(0, 0, 0)] * 9)
    with pytest.raises(ValueError, match="dimensions"):
        validate_png_capture(path, expected_width=4, expected_height=3)
