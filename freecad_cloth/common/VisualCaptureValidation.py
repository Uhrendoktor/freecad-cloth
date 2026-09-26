"""Structural validation for screenshots captured from FreeCAD GUI views."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path
from typing import Iterable, Tuple


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _unfilter_rows(raw: bytes, width: int, height: int, bytes_per_pixel: int) -> Iterable[bytes]:
    stride = width * bytes_per_pixel
    expected = (stride + 1) * height
    if len(raw) != expected:
        raise ValueError("PNG decompressed payload length does not match IHDR")

    previous = bytearray(stride)
    offset = 0
    for _ in range(height):
        filter_type = raw[offset]
        offset += 1
        encoded = raw[offset : offset + stride]
        offset += stride
        row = bytearray(stride)
        if filter_type == 0:
            row[:] = encoded
        elif filter_type == 1:
            for index, value in enumerate(encoded):
                left = row[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
                row[index] = (value + left) & 0xFF
        elif filter_type == 2:
            for index, value in enumerate(encoded):
                row[index] = (value + previous[index]) & 0xFF
        elif filter_type == 3:
            for index, value in enumerate(encoded):
                left = row[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
                up = previous[index]
                row[index] = (value + ((left + up) // 2)) & 0xFF
        elif filter_type == 4:
            for index, value in enumerate(encoded):
                left = row[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
                up = previous[index]
                up_left = previous[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
                predictor = left + up - up_left
                pa = abs(predictor - left)
                pb = abs(predictor - up)
                pc = abs(predictor - up_left)
                preferred = left if pa <= pb and pa <= pc else up if pb <= pc else up_left
                row[index] = (value + preferred) & 0xFF
        else:
            raise ValueError("unsupported PNG filter type %d" % filter_type)
        previous = row
        yield bytes(row)


def _parse_png(path: Path) -> Tuple[int, int, bytes, int]:
    data = path.read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("invalid PNG signature")
    offset = len(PNG_SIGNATURE)
    width = height = None
    bit_depth = color_type = interlace = None
    idat = bytearray()
    saw_iend = False

    while offset + 12 <= len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        end = offset + 12 + length
        if end > len(data):
            raise ValueError("truncated PNG chunk")
        payload = data[offset + 8 : offset + 8 + length]
        crc = struct.unpack(">I", data[offset + 8 + length : end])[0]
        if (zlib.crc32(kind + payload) & 0xFFFFFFFF) != crc:
            raise ValueError("PNG chunk CRC mismatch")
        if kind == b"IHDR":
            if length != 13 or width is not None:
                raise ValueError("invalid PNG IHDR")
            width, height, bit_depth, color_type, compression, filt, interlace = struct.unpack(
                ">IIBBBBB", payload
            )
            if compression != 0 or filt != 0:
                raise ValueError("unsupported PNG compression/filter method")
        elif kind == b"IDAT":
            idat.extend(payload)
        elif kind == b"IEND":
            saw_iend = True
            break
        offset = end

    if not saw_iend or width is None or height is None:
        raise ValueError("incomplete PNG")
    if bit_depth != 8 or color_type not in (2, 6) or interlace != 0:
        raise ValueError("unsupported PNG pixel format")
    if not idat:
        raise ValueError("PNG has no image data")
    return width, height, zlib.decompress(bytes(idat)), 3 if color_type == 2 else 4


def validate_png_capture(
    path: Path,
    *,
    expected_width: int,
    expected_height: int,
    min_nonwhite_pixels: int = 64,
    min_distinct_rgb: int = 8,
) -> dict:
    """Validate a GUI screenshot structurally and reject empty/uniform captures."""
    width, height, raw, bytes_per_pixel = _parse_png(path)
    if (width, height) != (expected_width, expected_height):
        raise ValueError(
            "PNG dimensions are %dx%d, expected %dx%d"
            % (width, height, expected_width, expected_height)
        )

    nonwhite_pixels = 0
    colors = set()
    for row in _unfilter_rows(raw, width, height, bytes_per_pixel):
        for index in range(0, len(row), bytes_per_pixel):
            rgb = tuple(row[index : index + 3])
            colors.add(rgb)
            if min(rgb) < 250:
                nonwhite_pixels += 1

    if nonwhite_pixels < min_nonwhite_pixels:
        raise ValueError(
            "PNG content is effectively blank: nonwhite_pixels=%d minimum=%d"
            % (nonwhite_pixels, min_nonwhite_pixels)
        )
    if len(colors) < min_distinct_rgb:
        raise ValueError(
            "PNG content is effectively uniform: distinct_rgb=%d minimum=%d"
            % (len(colors), min_distinct_rgb)
        )

    return {
        "width": width,
        "height": height,
        "nonwhite_pixels": nonwhite_pixels,
        "distinct_rgb": len(colors),
    }
