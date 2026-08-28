"""Dependency-free deterministic interchange for sewing pattern geometry."""
from html import escape
from PatternGeometry import ParametricPattern


def _outline(pattern: ParametricPattern, curve_samples: int):
    points = pattern.sampled_outline(curve_samples)
    if not points:
        raise ValueError("pattern has no outline")
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    width = max_x - min_x
    height = max_y - min_y
    if width <= 0 or height <= 0:
        raise ValueError("pattern must have non-zero extent")
    return points, min_x, min_y, width, height


def to_svg(pattern: ParametricPattern, curve_samples: int = 32, units: str = "mm") -> str:
    if not units:
        raise ValueError("units must not be empty")
    points, min_x, min_y, width, height = _outline(pattern, curve_samples)

    def fmt(p):
        return f"{p[0]-min_x:.6f},{height-(p[1]-min_y):.6f}"

    d = "M " + " L ".join(fmt(p) for p in points) + " Z"
    edge_ids = " ".join(escape(s.id) for s in pattern.segments)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:g}{escape(units)}" '
            f'height="{height:g}{escape(units)}" viewBox="0 0 {width:.6f} {height:.6f}" '
            f'data-units="{escape(units)}" data-edge-ids="{edge_ids}">'
            f'<path id="sewing-boundary" d="{d}" fill="none" stroke="black"/>\n</svg>')


def to_dxf(pattern: ParametricPattern, curve_samples: int = 32, units: str = "mm") -> str:
    """Return deterministic ASCII R12 DXF polyline with sewing metadata.

    Coordinates are translated to a non-negative local origin.  Edge IDs and
    units are retained in DXF group-code-999 comments so a consumer can round
    trip construction metadata without depending on a DXF library.
    """
    if not units:
        raise ValueError("units must not be empty")
    points, min_x, min_y, _, _ = _outline(pattern, curve_samples)
    edge_ids = ",".join(s.id.replace("\n", " ").replace("\r", " ") for s in pattern.segments)
    lines = [
        "0", "SECTION", "2", "HEADER",
        "9", "$ACADVER", "1", "AC1009",
        "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES",
        "999", "FREECAD_CLOTH_UNITS=" + units.replace("\n", " ").replace("\r", " "),
        "999", "FREECAD_CLOTH_EDGE_IDS=" + edge_ids,
        "0", "POLYLINE", "8", "SEWING_PATTERN", "66", "1", "70", "1",
    ]
    for x, y in points:
        lines.extend(["0", "VERTEX", "8", "SEWING_PATTERN", "10", f"{x - min_x:.6f}",
                      "20", f"{y - min_y:.6f}", "30", "0.000000"])
    lines.extend(["0", "SEQEND", "0", "ENDSEC", "0", "EOF"])
    return "\n".join(lines) + "\n"


def dxf_metadata(dxf: str):
    """Extract the FreeCAD Cloth metadata comments emitted by :func:`to_dxf`."""
    values = {"units": None, "edge_ids": ()}
    for line in dxf.splitlines():
        if line.startswith("FREECAD_CLOTH_UNITS="):
            values["units"] = line.split("=", 1)[1]
        elif line.startswith("FREECAD_CLOTH_EDGE_IDS="):
            raw = line.split("=", 1)[1]
            values["edge_ids"] = tuple(item for item in raw.split(",") if item)
    return values
