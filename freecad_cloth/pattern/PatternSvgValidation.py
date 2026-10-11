"""Independent QtSvg rendering and physical-dimension checks for pattern SVGs."""

import math
import re
from pathlib import Path
from types import ModuleType
from xml.etree import ElementTree


_MM_LENGTH = re.compile(r"^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)mm\s*$")


def _parse_mm_length(value: str, name: str) -> float:
    """Parse a physical SVG length expressed in millimetres."""
    match = _MM_LENGTH.fullmatch(value)
    if match is None:
        raise ValueError(f"SVG {name} must be expressed in millimetres")
    length = float(match.group(1))
    if not math.isfinite(length) or length <= 0.0:
        raise ValueError(f"SVG {name} must be finite and positive")
    return length


def _qt_modules() -> tuple[ModuleType, ModuleType, ModuleType]:
    """Load the Qt SVG modules supported by FreeCAD without a module-level Qt dependency."""
    try:
        from PySide import QtCore, QtGui, QtSvg
    except ImportError:
        try:
            from PySide2 import QtCore, QtGui, QtSvg
        except ImportError as exc:
            raise RuntimeError(
                "independent SVG validation requires FreeCAD's QtSvg modules"
            ) from exc
    return QtCore, QtGui, QtSvg


def render_svg_for_validation(
    svg: str,
    *,
    dpi: int = 96,
    output_path: str | Path | None = None,
) -> dict[str, object]:
    """Validate physical SVG sizing and render it independently with QtSvg.

    SVG dimensions and viewBox units are checked before rendering. The raster is
    then sized from the declared physical millimetre dimensions and rendered by
    QtSvg, rather than by the application's own path-generation code.
    """
    if not isinstance(svg, str) or not svg.strip():
        raise ValueError("SVG content must not be empty")
    if isinstance(dpi, bool) or not isinstance(dpi, int) or not 36 <= dpi <= 600:
        raise ValueError("SVG validation DPI must be an integer between 36 and 600")

    try:
        root = ElementTree.fromstring(svg)
    except ElementTree.ParseError as exc:
        raise ValueError("SVG is not well-formed XML") from exc
    if root.tag.rsplit("}", 1)[-1] != "svg":
        raise ValueError("document root is not SVG")

    width_mm = _parse_mm_length(root.attrib.get("width", ""), "width")
    height_mm = _parse_mm_length(root.attrib.get("height", ""), "height")
    if root.attrib.get("data-units") != "mm":
        raise ValueError("SVG data-units must declare millimetres")

    viewbox_values = root.attrib.get("viewBox", "").replace(",", " ").split()
    if len(viewbox_values) != 4:
        raise ValueError("SVG viewBox must contain four finite numbers")
    try:
        viewbox = tuple(float(value) for value in viewbox_values)
    except ValueError as exc:
        raise ValueError("SVG viewBox must contain four finite numbers") from exc
    if not all(math.isfinite(value) for value in viewbox):
        raise ValueError("SVG viewBox must contain four finite numbers")
    view_x, view_y, view_width, view_height = viewbox
    if abs(view_x) > 1e-8 or abs(view_y) > 1e-8:
        raise ValueError("SVG viewBox origin must be (0, 0) for physical-scale export")
    width_tolerance = max(1e-6, width_mm * 1e-6)
    height_tolerance = max(1e-6, height_mm * 1e-6)
    if abs(view_width - width_mm) > width_tolerance:
        raise ValueError("SVG physical width does not match its viewBox width")
    if abs(view_height - height_mm) > height_tolerance:
        raise ValueError("SVG physical height does not match its viewBox height")

    QtCore, QtGui, QtSvg = _qt_modules()
    encoded = QtCore.QByteArray(svg.encode("utf-8"))
    renderer = QtSvg.QSvgRenderer(encoded)
    if not renderer.isValid():
        raise ValueError("QtSvg could not independently render the SVG document")

    # Round upward so the raster never represents less than the declared physical extent.
    pixel_width = max(1, math.ceil(width_mm * dpi / 25.4))
    pixel_height = max(1, math.ceil(height_mm * dpi / 25.4))
    image_format = QtGui.QImage.Format_ARGB32
    image = QtGui.QImage(pixel_width, pixel_height, image_format)
    if image.isNull():
        raise RuntimeError("QtSvg validation could not allocate its raster image")
    image.fill(QtGui.QColor(255, 255, 255, 255))
    painter = QtGui.QPainter(image)
    if not painter.isActive():
        raise RuntimeError("QtSvg validation could not begin raster painting")
    try:
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        renderer.render(painter, QtCore.QRectF(0.0, 0.0, float(pixel_width), float(pixel_height)))
    finally:
        painter.end()

    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("SVG render validation requires NumPy for raster inspection") from exc

    bits = image.bits()
    byte_count = image.byteCount()
    if hasattr(bits, "setsize"):
        bits.setsize(byte_count)
    raw = bytes(bits)
    row_stride = image.bytesPerLine()
    if len(raw) < row_stride * pixel_height:
        raise RuntimeError("QtSvg returned an incomplete raster buffer")
    pixels = np.frombuffer(raw, dtype=np.uint8).reshape(pixel_height, row_stride)
    pixels = pixels[:, : pixel_width * 4].reshape(pixel_height, pixel_width, 4)
    ink = np.any(pixels[:, :, :3] < 245, axis=2)
    ink_y, ink_x = np.nonzero(ink)
    ink_pixel_count = int(ink_x.size)
    if ink_pixel_count == 0:
        raise ValueError("QtSvg rendered no visible pattern linework")

    bounds = [
        int(ink_x.min()),
        int(ink_y.min()),
        int(ink_x.max()),
        int(ink_y.max()),
    ]
    viewport_edges = []
    if bounds[0] == 0:
        viewport_edges.append("left")
    if bounds[1] == 0:
        viewport_edges.append("top")
    if bounds[2] >= pixel_width - 1:
        viewport_edges.append("right")
    if bounds[3] >= pixel_height - 1:
        viewport_edges.append("bottom")

    saved_path = ""
    if output_path is not None:
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not image.save(str(target), "PNG"):
            raise OSError(f"could not write SVG validation preview: {target}")
        saved_path = str(target)

    raster_width_mm = pixel_width * 25.4 / dpi
    raster_height_mm = pixel_height * 25.4 / dpi
    return {
        "valid": True,
        "renderer": "QtSvg",
        "dpi": dpi,
        "physical_width_mm": width_mm,
        "physical_height_mm": height_mm,
        "viewbox": [view_x, view_y, view_width, view_height],
        "raster_width_px": pixel_width,
        "raster_height_px": pixel_height,
        "raster_width_mm": raster_width_mm,
        "raster_height_mm": raster_height_mm,
        "raster_rounding_error_mm": [
            raster_width_mm - width_mm,
            raster_height_mm - height_mm,
        ],
        "ink_pixel_count": ink_pixel_count,
        "ink_bounds_px": bounds,
        "ink_touches_viewport_edges": viewport_edges,
        "png_path": saved_path,
    }
