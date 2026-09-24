"""FreeCAD document objects for sewing operations."""
import ast
from math import atan2, degrees, hypot

from freecad_cloth.sewing.SewingCorrespondence import analyze_correspondence, correspondence_recovery, correspondence_status_label


def _outline_points(piece):
    """Return the ordered sewing boundary as 2D points."""
    for attr in ("SewingOutline", "DraftingBoundary"):
        raw = getattr(piece, attr, "")
        if raw:
            try:
                values = ast.literal_eval(str(raw))
                points = [(float(p[0]), float(p[1])) for p in values]
                if len(points) >= 3:
                    return points
            except (ValueError, SyntaxError, TypeError, IndexError):
                pass
    width, height = float(piece.Width), float(piece.Height)
    return [(0.0, 0.0), (width, 0.0), (width, height), (0.0, height)]


def _native_edge(piece, edge):
    """Return the authoritative native Sketcher/Shape edge when available."""
    try:
        index = int(edge)
        if str(getattr(piece, "GeometryAuthority", "")) == "Sketcher":
            sketch = getattr(piece, "Sketch", None)
            sketch_shape = getattr(sketch, "Shape", None) if sketch is not None else None
            sketch_edges = getattr(sketch_shape, "Edges", None)
            if sketch_edges is not None and 0 <= index < len(sketch_edges):
                return sketch_edges[index]
        shape = getattr(piece, "Shape", None)
        edges = getattr(shape, "Edges", None)
        if edges is None:
            return None
        outline = _outline_points(piece)
        if 0 <= index < len(edges) and len(edges) == len(outline):
            return edges[index]
    except (TypeError, ValueError, IndexError):
        pass
    return None


def _edge_polyline(piece, edge, sample_count=64):
    """Return a local 2D polyline suitable for arc-length operations."""
    edge = int(edge)
    native = _native_edge(piece, edge)
    if native is not None:
        try: