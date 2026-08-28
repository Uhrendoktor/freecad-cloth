"""Deterministic SVG and DXF interchange for sewing-pattern geometry.

The pattern boundary is the source of truth. Exporters only serialize the
current sewing boundary plus optional derived cut geometry and semantic
metadata; they do not mutate the pattern model.
"""
from html import escape
import json
import re
from typing import Any, Mapping

from PatternGeometry import ParametricPattern, LineSegment, QuadraticBezier


_DXF_UNITS = {"in": 1, "inch": 1, "mm": 4, "cm": 5, "m": 6}


def build_export_metadata(
    pattern: ParametricPattern,
    units: str = "mm",
    derived: Any = None,
    extra: Mapping[str, Any] | None = None,
) -> dict:
    """Build the stable metadata payload shared by SVG and DXF exports."""
    if not units:
        raise ValueError("units must not be empty")
    metadata = {
        "schema": "freecad-cloth.pattern-export.v1",
        "units": units,
        "edge_ids": [segment.id for segment in pattern.segments],
        "notches": [],
    }
    if derived is not None:
        metadata["notches"] = [
            {
                "id": notch.id,
                "segment_id": notch.segment_id,
                "position": float(notch.t),
                "depth": float(notch.depth),
            }
            for notch in derived.notches
        ]
        metadata["has_cut_boundary"] = bool(derived.cut_boundary)
    else:
        metadata["has_cut_boundary"] = False
    if extra:
        metadata["extra"] = dict(extra)
    return metadata


def _fmt(value: float) -> str:
    return f"{float(value):.6f}".rstrip("0").rstrip(".") or "0"


def _bounds(paths):
    points = [point for path in paths for point in path]
    if not points:
        raise ValueError("pattern has no outline")
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), max(xs), min(ys), max(ys)


def to_svg(
    pattern: ParametricPattern,
    curve_samples: int = 32,
    units: str = "mm",
    derived: Any = None,
    metadata: Mapping[str, Any] | None = None,
) -> str:
    """Serialize sewing/cut boundaries and semantic metadata to deterministic SVG."""
    if not units:
        raise ValueError("units must not be empty")
    sewing_points = pattern.sampled_outline(curve_samples)
    if not sewing_points:
        raise ValueError("pattern has no outline")
    paths = [sewing_points]
    cut_paths = []
    if derived is not None:
        cut_paths = [list(edge.points) for edge in derived.cut_boundary if edge.points]
        paths.extend(cut_paths)
    min_x, max_x, min_y, max_y = _bounds(paths)
    width = max_x - min_x
    height = max_y - min_y
    if width <= 0 or height <= 0:
        raise ValueError("pattern must have non-zero extent")

    def svg_path(points, closed):
        def fmt(point):
            return f"{_fmt(point[0] - min_x)},{_fmt(max_y - point[1])}"
        return "M " + " L ".join(fmt(point) for point in points) + (" Z" if closed else "")

    payload = build_export_metadata(pattern, units, derived, metadata)
    metadata_json = escape(json.dumps(payload, sort_keys=True, separators=(",", ":")), quote=False)
    edge_ids = escape(" ".join(segment.id for segment in pattern.segments), quote=True)
    elements = [
        f'<path id="sewing-boundary" d="{svg_path(sewing_points, True)}" fill="none" stroke="black"/>',
    ]
    if cut_paths:
        for edge, points in zip(derived.cut_boundary, cut_paths):
            elements.append(
                f'<path id="cut-{escape(edge.id)}" data-edge-id="{escape(edge.id)}" '
                f'd="{svg_path(points, False)}" fill="none" stroke="black"/>'
            )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_fmt(width)}{escape(units)}" '
        f'height="{_fmt(height)}{escape(units)}" viewBox="0 0 {_fmt(width)} {_fmt(height)}" '
        f'data-units="{escape(units)}" data-edge-ids="{edge_ids}">'
        f'<metadata id="freecad-cloth-pattern">{metadata_json}</metadata>\n'
        + "\n".join(elements)
        + "\n</svg>"
    )


def to_dxf(
    pattern: ParametricPattern,
    curve_samples: int = 32,
    units: str = "mm",
    derived: Any = None,
    metadata: Mapping[str, Any] | None = None,
) -> str:
    """Serialize sewing/cut geometry as deterministic ASCII DXF."""
    if not units:
        raise ValueError("units must not be empty")
    if units.lower() not in _DXF_UNITS:
        raise ValueError(f"unsupported DXF units: {units}")
    payload = json.dumps(
        build_export_metadata(pattern, units, derived, metadata),
        sort_keys=True,
        separators=(",", ":"),
    )
    lines = [
        "0", "SECTION", "2", "HEADER", "9", "$INSUNITS", "70", str(_DXF_UNITS[units.lower()]),
        "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES",
    ]

    def add_polyline(points, layer, closed):
        if len(points) < 2:
            return
        lines.extend(["0", "POLYLINE", "8", layer, "66", "1", "70", "1" if closed else "0"])
        for x, y in points:
            lines.extend(["0", "VERTEX", "8", layer, "10", _fmt(x), "20", _fmt(y), "30", "0"])
        lines.extend(["0", "SEQEND"])

    add_polyline(pattern.sampled_outline(curve_samples), "SEWING", True)
    if derived is not None:
        for edge in derived.cut_boundary:
            add_polyline(edge.points, "CUT_" + _safe_layer(edge.id), False)
        for notch in derived.notches:
            point = notch_point(pattern, notch)
            lines.extend(["0", "POINT", "8", "NOTCH", "10", _fmt(point[0]), "20", _fmt(point[1]), "30", "0"])

    # Group code 999 is an R12-compatible comment. Keep it before ENDSEC/EOF
    # so parsers that stop at EOF still retain the semantic document payload.
    lines.extend(["999", "FREECAD_CLOTH_METADATA " + payload, "0", "ENDSEC", "0", "EOF"])
    return "\n".join(lines) + "\n"


def notch_point(pattern, notch):
    notch.validate()
    segment = pattern.by_id().get(notch.segment_id)
    if segment is None:
        raise ValueError(f"notch references unknown segment: {notch.segment_id}")
    return segment.point(notch.t)


def extract_metadata(text: str) -> dict:
    """Read the shared metadata payload from an SVG or DXF export."""
    svg_match = re.search(r'<metadata id="freecad-cloth-pattern">(.*?)</metadata>', text, re.DOTALL)
    if svg_match:
        return json.loads(svg_match.group(1))
    dxf_match = re.search(r"^999\nFREECAD_CLOTH_METADATA (.+)$", text, re.MULTILINE)
    if dxf_match:
        return json.loads(dxf_match.group(1))
    raise ValueError("freecad-cloth export metadata not found")


def _safe_layer(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_$-]", "_", str(value))
    return cleaned[:200] or "EDGE"
