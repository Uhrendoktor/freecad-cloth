"""Dependency-free SVG interchange for sewing pattern geometry."""
from html import escape
from PatternGeometry import ParametricPattern, LineSegment


def to_svg(pattern: ParametricPattern, curve_samples: int = 32, units: str = "mm") -> str:
    if not units:
        raise ValueError("units must not be empty")
    points = pattern.sampled_outline(curve_samples)
    if not points:
        raise ValueError("pattern has no outline")
    xs = [p[0] for p in points]; ys = [p[1] for p in points]
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    width = max_x - min_x; height = max_y - min_y
    if width <= 0 or height <= 0:
        raise ValueError("pattern must have non-zero extent")
    def fmt(p): return f"{p[0]-min_x:.6f},{height-(p[1]-min_y):.6f}"
    d = "M " + " L ".join(fmt(p) for p in points) + " Z"
    edge_ids = " ".join(escape(s.id) for s in pattern.segments)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:g}{escape(units)}" '
            f'height="{height:g}{escape(units)}" viewBox="0 0 {width:.6f} {height:.6f}" '
            f'data-units="{escape(units)}" data-edge-ids="{edge_ids}">'
            f'<path id="sewing-boundary" d="{d}" fill="none" stroke="black"/>\n</svg>')
