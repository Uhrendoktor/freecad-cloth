"""Dependency-free, deterministic SVG/DXF interchange for sewing patterns."""
import json
from html import escape
from math import cos, radians, sin

from PatternDerivedGeometry import DerivedPattern, mark_point, notch_point
from PatternGeometry import ParametricPattern


def _fmt(value):
    return f"{float(value):.6f}"


def _sampled_sewing(pattern, curve_samples):
    points = pattern.sampled_outline(curve_samples)
    if not points:
        raise ValueError("pattern has no outline")
    return points


def to_svg(pattern: ParametricPattern, curve_samples: int = 32, units: str = "mm", derived: DerivedPattern | None = None) -> str:
    """Serialize sewing/cut boundaries and semantic marks to deterministic SVG."""
    if not units.strip():
        raise ValueError("units must not be empty")
    sewing = _sampled_sewing(pattern, curve_samples)
    if derived is not None and derived.sewing_boundary is not pattern:
        raise ValueError("derived pattern belongs to a different sewing boundary")
    cut_edges = derived.cut_boundary if derived is not None else ()
    xs = [p[0] for p in sewing]
    ys = [p[1] for p in sewing]
    for edge in cut_edges:
        xs.extend(p[0] for p in edge.points)
        ys.extend(p[1] for p in edge.points)
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    width, height = max_x - min_x, max_y - min_y
    if width <= 0 or height <= 0:
        raise ValueError("pattern must have non-zero extent")

    def xy(point):
        return (point[0] - min_x, height - (point[1] - min_y))

    def path(points, closed=True):
        coords = [xy(p) for p in points]
        suffix = " Z" if closed else ""
        return "M " + " L ".join(f"{_fmt(x)},{_fmt(y)}" for x, y in coords) + suffix

    edge_ids = " ".join(escape(s.id, quote=True) for s in pattern.segments)
    metadata = json.dumps({"version": 1, "units": units, "edge_ids": [s.id for s in pattern.segments]}, sort_keys=True, separators=(",", ":"))
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_fmt(width)}{escape(units)}" height="{_fmt(height)}{escape(units)}" viewBox="0 0 {_fmt(width)} {_fmt(height)}" data-units="{escape(units, quote=True)}" data-edge-ids="{edge_ids}">',
        f'  <metadata>{escape(metadata)}</metadata>',
        f'  <g id="sewing-boundary" data-edge-ids="{edge_ids}"><path d="{path(sewing)}" fill="none"/></g>',
    ]
    if cut_edges:
        lines.append('  <g id="cut-boundary">')
        for edge in cut_edges:
            lines.append(f'    <path id="cut-{escape(edge.id, quote=True)}" d="{path(edge.points, False)}" fill="none"/>')
        lines.append('  </g>')
    if derived is not None and (derived.notches or derived.marks):
        lines.append('  <g id="construction-marks">')
        for notch in derived.notches:
            x, y = xy(notch_point(pattern, notch))
            lines.append(f'    <circle id="notch-{escape(notch.id, quote=True)}" cx="{_fmt(x)}" cy="{_fmt(y)}" r="{_fmt(max(0.5, notch.depth / 4))}" data-segment="{escape(notch.segment_id, quote=True)}" data-t="{_fmt(notch.t)}"/>')
        for mark in derived.marks:
            x, y = xy(mark_point(pattern, mark))
            angle = radians(mark.angle)
            half = mark.length / 2.0
            dx, dy = cos(angle) * half, -sin(angle) * half
            lines.append(f'    <line id="mark-{escape(mark.id, quote=True)}" x1="{_fmt(x-dx)}" y1="{_fmt(y-dy)}" x2="{_fmt(x+dx)}" y2="{_fmt(y+dy)}" data-kind="{escape(mark.kind, quote=True)}" data-segment="{escape(mark.segment_id, quote=True)}" data-t="{_fmt(mark.t)}"/>')
            if mark.text:
                lines.append(f'    <text x="{_fmt(x)}" y="{_fmt(y)}" data-mark-id="{escape(mark.id, quote=True)}">{escape(mark.text)}</text>')
        lines.append('  </g>')
    lines.append('</svg>')
    return "\n".join(lines) + "\n"


def to_dxf(pattern: ParametricPattern, curve_samples: int = 32, units: str = "mm", derived: DerivedPattern | None = None) -> str:
    """Serialize deterministic ASCII DXF using SEWING/CUT/MARK layers."""
    if not units.strip():
        raise ValueError("units must not be empty")
    sewing = _sampled_sewing(pattern, curve_samples)
    if derived is not None and derived.sewing_boundary is not pattern:
        raise ValueError("derived pattern belongs to a different sewing boundary")

    entities = []
    def polyline(points, layer, closed=True):
        pts = list(points)
        if closed and pts[-1] != pts[0]:
            pts.append(pts[0])
        values = ["0", "LWPOLYLINE", "8", layer, "90", str(len(pts)), "70", "1" if closed else "0"]
        for x, y in pts:
            values += ["10", _fmt(x), "20", _fmt(y)]
        entities.append(values)

    polyline(sewing, "SEWING", True)
    if derived is not None:
        for edge in derived.cut_boundary:
            polyline(edge.points, "CUT", False)
        for notch in derived.notches:
            x, y = notch_point(pattern, notch)
            polyline([(x, y), (x, y + notch.depth)], "MARK", False)
        for mark in derived.marks:
            x, y = mark_point(pattern, mark)
            angle = radians(mark.angle)
            dx, dy = cos(angle) * mark.length / 2.0, sin(angle) * mark.length / 2.0
            polyline([(x-dx, y-dy), (x+dx, y+dy)], "MARK", False)

    metadata = json.dumps({"version": 1, "units": units, "edge_ids": [s.id for s in pattern.segments]}, sort_keys=True, separators=(",", ":"))
    lines = ["0", "SECTION", "2", "HEADER", "9", "$COMMENT", "1", metadata, "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]
    for entity in entities:
        lines.extend(entity)
    lines += ["0", "ENDSEC", "0", "EOF", ""]
    return "\n".join(lines)


def from_dxf_metadata(dxf: str) -> dict:
    """Read the canonical metadata record without requiring a DXF library."""
    marker = "$COMMENT\n1\n"
    if marker not in dxf:
        raise ValueError("DXF does not contain cloth-pattern metadata")
    payload = dxf.split(marker, 1)[1].split("\n0\nENDSEC", 1)[0].strip()
    data = json.loads(payload)
    if data.get("version") != 1 or not data.get("edge_ids"):
        raise ValueError("unsupported or incomplete cloth-pattern metadata")
    return data
