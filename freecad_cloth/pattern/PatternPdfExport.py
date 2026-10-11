"""Dependency-free deterministic tiled 1:1 vector PDF export for sewing patterns."""

from __future__ import annotations

import base64
import json
from math import ceil, cos, isfinite, radians, sin

from freecad_cloth.pattern.PatternDerivedGeometry import DerivedPattern, mark_point
from freecad_cloth.pattern.PatternGeometry import ParametricPattern, Point
from freecad_cloth.pattern.PatternExport import (
    _cut_contour_with_notches,
    _metadata,
    _sampled_sewing,
    _validate_units,
)

_MM_TO_PT = 72.0 / 25.4
_HEADER_MM = 10.0
_FOOTER_MM = 31.0
_CALIBRATION_MM = 25.0
_PAPER_SIZES_MM: dict[str, tuple[float, float]] = {
    "A4": (210.0, 297.0),
    "Letter": (215.9, 279.4),
}


def _number(value: float) -> str:
    if not isfinite(value):
        raise ValueError("PDF coordinates must be finite")
    if abs(value) < 0.000005:
        value = 0.0
    return f"{value:.5f}".rstrip("0").rstrip(".") or "0"


def _literal(value: str) -> str:
    """Return an ASCII-only PDF literal string using WinAnsi-compatible escapes."""
    encoded = value.encode("cp1252", errors="replace")
    escaped: list[str] = []
    for byte in encoded:
        if byte in (ord("("), ord(")"), ord("\\")):
            escaped.append("\\" + chr(byte))
        elif byte < 32 or byte > 126:
            escaped.append("\\" + "{:03o}".format(byte))
        else:
            escaped.append(chr(byte))
    return "(" + "".join(escaped) + ")"


def _tile_count(extent: float, usable: float, stride: float) -> int:
    remaining = max(0.0, extent - usable)
    return max(1, ceil(max(0.0, remaining - 1e-8) / stride) + 1)


def _document_bytes(
    page_streams: list[bytes],
    paper_width_mm: float,
    paper_height_mm: float,
    metadata: dict[str, object],
) -> bytes:
    """Build a small deterministic PDF 1.4 document with native vector streams."""
    encoded_metadata = json.dumps(
        metadata, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    header = (
        b"%PDF-1.4\n%ClothPatternMetadata:"
        + base64.b64encode(encoded_metadata)
        + b"\n%\xe2\xe3\xcf\xd3\n"
    )
    page_count = len(page_streams)
    font_id = 3 + page_count * 2
    info_id = font_id + 1
    objects: list[bytes] = [b""] * (info_id + 1)
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    kids = " ".join(f"{3 + index * 2} 0 R" for index in range(page_count))
    objects[2] = f"<< /Type /Pages /Kids [{kids}] /Count {page_count} >>".encode("ascii")
    media_width_pt = paper_width_mm * _MM_TO_PT
    media_height_pt = paper_height_mm * _MM_TO_PT
    media_box = f"[0 0 {_number(media_width_pt)} {_number(media_height_pt)}]".encode("ascii")
    for index, stream in enumerate(page_streams):
        page_id = 3 + index * 2
        stream_id = page_id + 1
        objects[page_id] = (
            b"<< /Type /Page /Parent 2 0 R /MediaBox "
            + media_box
            + b" /Resources << /Font << /F1 "
            + str(font_id).encode("ascii")
            + b" 0 R >> >> /Contents "
            + str(stream_id).encode("ascii")
            + b" 0 R >>"
        )
        objects[stream_id] = (
            b"<< /Length "
            + str(len(stream)).encode("ascii")
            + b" >>\nstream\n"
            + stream
            + b"\nendstream"
        )
    objects[font_id] = (
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
        b"/Encoding /WinAnsiEncoding >>"
    )
    objects[info_id] = (
        b"<< /Title "
        + _literal("Cloth pattern 1:1 tiled export").encode("ascii")
        + b" /Author "
        + _literal("FreeCAD Cloth").encode("ascii")
        + b" /Subject "
        + _literal("Vector pattern export; print at actual size / 100 percent").encode("ascii")
        + b" >>"
    )

    output = bytearray(header)
    offsets = [0] * len(objects)
    for object_id in range(1, len(objects)):
        offsets[object_id] = len(output)
        output.extend(f"{object_id} 0 obj\n".encode("ascii"))
        output.extend(objects[object_id])
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects)}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        (
            f"trailer\n<< /Size {len(objects)} /Root 1 0 R /Info {info_id} 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(output)


def from_pdf_metadata(pdf: bytes) -> dict[str, object]:
    """Read the deterministic Cloth metadata comment embedded in an exported PDF."""
    if not isinstance(pdf, bytes) or not pdf.startswith(b"%PDF-1.4"):
        raise ValueError("PDF is not a supported Cloth pattern export")
    marker = b"%ClothPatternMetadata:"
    line = next((item for item in pdf.splitlines() if item.startswith(marker)), None)
    if line is None:
        raise ValueError("PDF does not contain cloth-pattern metadata")
    try:
        payload = base64.b64decode(line[len(marker) :], validate=True)
        metadata = json.loads(payload.decode("ascii"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("PDF contains invalid cloth-pattern metadata") from exc
    if (
        metadata.get("version") != 1
        or metadata.get("units") != "mm"
        or metadata.get("scale") != 1.0
        or not metadata.get("edge_ids")
    ):
        raise ValueError("PDF contains unsupported or incomplete cloth-pattern metadata")
    return metadata


def to_pdf(
    pattern: ParametricPattern,
    curve_samples: int = 32,
    units: str = "mm",
    derived: DerivedPattern | None = None,
    piece_id: str = "",
    seam_ids: tuple[str, ...] = (),
    seam_allowance: float = 0.0,
    *,
    paper_size: str = "A4",
    margin_mm: float = 10.0,
    overlap_mm: float = 10.0,
) -> bytes:
    """Create a multi-page, actual-size vector PDF with registration and calibration marks.

    Pages are ordered from top-left across each row. The printable geometry is clipped
    to each tile; neighboring pages share registration crosses in their overlap. Every
    page carries a 25 mm calibration square and print-at-100-percent instructions.
    """
    normalized_units = _validate_units(units)
    if curve_samples < 2:
        raise ValueError("curve_samples must be at least 2")
    if derived is not None and derived.sewing_boundary is not pattern:
        raise ValueError("derived pattern belongs to a different sewing boundary")
    if not isfinite(seam_allowance) or seam_allowance < 0:
        raise ValueError("seam allowance must be finite and non-negative")
    paper_key = str(paper_size).strip().lower().replace("us ", "")
    paper_key = {"a4": "A4", "letter": "Letter"}.get(paper_key, "")
    if not paper_key:
        raise ValueError("paper_size must be 'A4' or 'Letter'")
    paper_width_mm, paper_height_mm = _PAPER_SIZES_MM[paper_key]
    margin = float(margin_mm)
    overlap = float(overlap_mm)
    if not isfinite(margin) or margin < 5.0:
        raise ValueError("PDF margin must be finite and at least 5 mm")
    if not isfinite(overlap) or overlap < 0.0:
        raise ValueError("PDF overlap must be finite and non-negative")

    content_left = margin
    content_bottom = margin + _FOOTER_MM
    content_right = paper_width_mm - margin
    content_top = paper_height_mm - margin - _HEADER_MM
    usable_width = content_right - content_left
    usable_height = content_top - content_bottom
    if usable_width <= 40.0 or usable_height <= _CALIBRATION_MM:
        raise ValueError("paper size and margins leave no usable pattern area")
    if overlap >= min(usable_width, usable_height):
        raise ValueError("PDF overlap must be smaller than the printable tile area")
    stride_x = usable_width - overlap
    stride_y = usable_height - overlap

    sewing = _sampled_sewing(pattern, curve_samples)
    cut = _cut_contour_with_notches(pattern, derived) if derived is not None else ()
    marks = tuple(derived.marks) if derived is not None else ()
    bound_points: list[Point] = [*sewing, *cut]
    mark_layout: list[tuple[object, float, float, float, float]] = []
    for mark in marks:
        x, y = mark_point(pattern, mark)
        half = float(mark.length) / 2.0
        dx = cos(radians(float(mark.angle))) * half
        dy = sin(radians(float(mark.angle))) * half
        bound_points.extend(((x - dx, y - dy), (x + dx, y + dy)))
        mark_layout.append((mark, x, y, dx, dy))
        if mark.text:
            bound_points.extend(
                ((x, y - 1.0), (x + max(2.0, len(mark.text) * 1.8), y + 2.0))
            )
    if not bound_points:
        raise ValueError("pattern has no geometry to export")
    if any(not isfinite(value) for point in bound_points for value in point):
        raise ValueError("pattern contains non-finite geometry")
    min_x = min(point[0] for point in bound_points)
    max_x = max(point[0] for point in bound_points)
    min_y = min(point[1] for point in bound_points)
    max_y = max(point[1] for point in bound_points)
    extent_width = max_x - min_x
    extent_height = max_y - min_y
    if extent_width <= 0.0 or extent_height <= 0.0:
        raise ValueError("pattern must have non-zero extent")

    columns = _tile_count(extent_width, usable_width, stride_x)
    rows = _tile_count(extent_height, usable_height, stride_y)
    page_count = columns * rows
    metadata = _metadata(
        pattern, normalized_units, piece_id, seam_ids, derived, seam_allowance
    )
    metadata.update(
        {
            "format": "pdf",
            "units": "mm",
            "scale": 1.0,
            "seam_allowance_mm": float(seam_allowance),
            "notch_ids": [str(notch.id) for notch in derived.notches] if derived else [],
            "mark_ids": [str(mark.id) for mark in marks],
            "paper_size": paper_key,
            "margin_mm": margin,
            "overlap_mm": overlap,
            "calibration_square_mm": _CALIBRATION_MM,
            "tile_columns": columns,
            "tile_rows": rows,
            "page_count": page_count,
        }
    )

    registrations: list[tuple[str, float, float]] = []
    if overlap >= 4.0:
        for row in range(rows):
            for column in range(columns - 1):
                registrations.append(
                    (
                        f"H{row + 1}-{column + 1}",
                        min_x + (column + 1) * stride_x + overlap / 2.0,
                        max_y - row * stride_y - usable_height / 2.0,
                    )
                )
        for row in range(rows - 1):
            for column in range(columns):
                registrations.append(
                    (
                        f"V{row + 1}-{column + 1}",
                        min_x + column * stride_x + usable_width / 2.0,
                        max_y - row * stride_y - usable_height + overlap / 2.0,
                    )
                )

    page_streams: list[bytes] = []
    for row in range(rows):
        for column in range(columns):
            tile_left = min_x + column * stride_x
            tile_top = max_y - row * stride_y
            tile_bottom = tile_top - usable_height
            commands: list[str] = [
                "q",
                (
                    f"{_number(content_left * _MM_TO_PT)} "
                    f"{_number(content_bottom * _MM_TO_PT)} "
                    f"{_number(usable_width * _MM_TO_PT)} "
                    f"{_number(usable_height * _MM_TO_PT)} re W n"
                ),
                "0 0 0 RG",
                "1 J",
                "1 j",
            ]

            def page_point(point: Point) -> tuple[float, float]:
                return (
                    (content_left + point[0] - tile_left) * _MM_TO_PT,
                    (content_bottom + point[1] - tile_bottom) * _MM_TO_PT,
                )

            def draw_polyline(
                points: tuple[Point, ...] | list[Point],
                *,
                closed: bool,
                width_mm: float,
                dashed: bool = False,
            ) -> None:
                if len(points) < 2:
                    return
                commands.append(f"{_number(width_mm * _MM_TO_PT)} w")
                commands.append("[5 3] 0 d" if dashed else "[] 0 d")
                x, y = page_point(points[0])
                commands.append(f"{_number(x)} {_number(y)} m")
                for point in points[1:]:
                    x, y = page_point(point)
                    commands.append(f"{_number(x)} {_number(y)} l")
                if closed:
                    commands.append("h")
                commands.append("S")
                commands.append("[] 0 d")

            def draw_text_pt(x_pt: float, y_pt: float, text: str, size_pt: float) -> None:
                commands.append(
                    f"BT /F1 {_number(size_pt)} Tf {_number(x_pt)} {_number(y_pt)} Td "
                    f"{_literal(text)} Tj ET"
                )

            def draw_page_text(x_mm: float, y_mm: float, text: str, size_pt: float) -> None:
                draw_text_pt(x_mm * _MM_TO_PT, y_mm * _MM_TO_PT, text, size_pt)

            draw_polyline(sewing, closed=True, width_mm=0.2, dashed=True)
            if cut:
                draw_polyline(cut, closed=True, width_mm=0.3)
            for mark, x, y, dx, dy in mark_layout:
                draw_polyline(
                    [(x - dx, y - dy), (x + dx, y + dy)],
                    closed=False,
                    width_mm=0.2,
                )
                if mark.text:
                    label_x, label_y = page_point((x + 1.0, y + 1.0))
                    draw_text_pt(label_x, label_y, str(mark.text), 3.0 * _MM_TO_PT)

            tick = 3.0
            for corner_x, corner_y, sign_x, sign_y in (
                (tile_left, tile_bottom, 1.0, 1.0),
                (tile_left + usable_width, tile_bottom, -1.0, 1.0),
                (tile_left, tile_top, 1.0, -1.0),
                (tile_left + usable_width, tile_top, -1.0, -1.0),
            ):
                draw_polyline(
                    [(corner_x, corner_y), (corner_x + sign_x * tick, corner_y)],
                    closed=False,
                    width_mm=0.2,
                )
                draw_polyline(
                    [(corner_x, corner_y), (corner_x, corner_y + sign_y * tick)],
                    closed=False,
                    width_mm=0.2,
                )

            for label, reg_x, reg_y in registrations:
                if (
                    tile_left - 1e-8 <= reg_x <= tile_left + usable_width + 1e-8
                    and tile_bottom - 1e-8 <= reg_y <= tile_top + 1e-8
                ):
                    cross = min(1.5, max(0.4, overlap / 4.0))
                    draw_polyline(
                        [(reg_x - cross, reg_y), (reg_x + cross, reg_y)],
                        closed=False,
                        width_mm=0.2,
                    )
                    draw_polyline(
                        [(reg_x, reg_y - cross), (reg_x, reg_y + cross)],
                        closed=False,
                        width_mm=0.2,
                    )
                    if overlap >= 8.0:
                        label_x, label_y = page_point((reg_x - 3.5, reg_y + 2.0))
                        draw_text_pt(label_x, label_y, label, 5.0)

            commands.append("Q")
            page_label = str(piece_id or "Pattern")[:42]
            draw_page_text(
                margin,
                paper_height_mm - margin - 6.5,
                f"{page_label} | Tile {column + 1}/{columns}, row {row + 1}/{rows} | 1:1",
                8.0,
            )

            calibration_x = margin
            calibration_y = margin + 3.0
            calibration_size_pt = _CALIBRATION_MM * _MM_TO_PT
            commands.append("0.6 w")
            commands.append(
                f"{_number(calibration_x * _MM_TO_PT)} "
                f"{_number(calibration_y * _MM_TO_PT)} "
                f"{_number(calibration_size_pt)} {_number(calibration_size_pt)} re S"
            )
            footer_x = margin + 31.0
            draw_page_text(footer_x, margin + 24.0, "25 mm CALIBRATION SQUARE", 7.0)
            draw_page_text(
                footer_x,
                margin + 16.0,
                "Print at ACTUAL SIZE / 100%; disable Fit to Page.",
                7.0,
            )
            draw_page_text(
                footer_x,
                margin + 8.0,
                f"Overlap: {_number(overlap)} mm. Match equal registration labels.",
                7.0,
            )
            page_streams.append(("\n".join(commands) + "\n").encode("ascii"))

    return _document_bytes(page_streams, paper_width_mm, paper_height_mm, metadata)


def validate_pdf_export(
    pattern: ParametricPattern,
    exported: bytes,
    curve_samples: int = 32,
    units: str = "mm",
    derived: DerivedPattern | None = None,
    piece_id: str = "",
    seam_ids: tuple[str, ...] = (),
    seam_allowance: float = 0.0,
    *,
    paper_size: str = "A4",
    margin_mm: float = 10.0,
    overlap_mm: float = 10.0,
) -> dict[str, object]:
    """Validate the PDF against a deterministic rerender from authoritative geometry."""
    expected = to_pdf(
        pattern,
        curve_samples,
        units,
        derived,
        piece_id,
        seam_ids,
        seam_allowance,
        paper_size=paper_size,
        margin_mm=margin_mm,
        overlap_mm=overlap_mm,
    )
    if exported != expected:
        raise ValueError("PDF does not match the deterministic authoritative pattern output")
    return {"format": "pdf", "valid": True, "metadata": from_pdf_metadata(exported)}
