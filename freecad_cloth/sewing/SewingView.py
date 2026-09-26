"""Small, FreeCAD-independent helpers for Sewing workbench views."""
from colorsys import hsv_to_rgb




_SEAM_GOLDEN_ANGLE = 0.618033988749895


def seam_color_map(seam_ids):
    """Return deterministic, visually distinct colors keyed by seam id."""
    ids = sorted({str(seam_id) for seam_id in seam_ids if str(seam_id).strip()})
    result = {}
    for index, seam_id in enumerate(ids):
        hue = (index * _SEAM_GOLDEN_ANGLE) % 1.0
        rgb = hsv_to_rgb(hue, 0.78, 0.92)
        result[seam_id] = tuple(round(channel, 6) for channel in rgb)
    return result


def apply_seam_colors(objects):
    """Apply one deterministic line color to each canonical seam object."""
    seam_objects = [
        obj for obj in objects
        if str(getattr(obj, "SeamId", "")).strip()
    ]
    colors = seam_color_map(getattr(obj, "SeamId", "") for obj in seam_objects)
    for obj in seam_objects:
        view = getattr(obj, "ViewObject", None)
        color = colors.get(str(getattr(obj, "SeamId", "")))
        if view is not None and color is not None:
            view.LineColor = color
    return colors


def refresh_seam_colors(document=None):
    """Refresh every canonical seam/operation color from its persistent SeamId."""
    if document is None:
        try:
            import FreeCAD as App
            document = App.ActiveDocument
        except ImportError:
            document = None
    if document is None:
        return {}
    return apply_seam_colors(document.Objects)


def pattern_pieces_for_2d(objects):
    """Return pattern pieces participating in the sewing 2D focus.

    The sewing view is a presentation of the authoritative pattern geometry,
    so PatternPiece objects are included alongside seam/network overlays.
    Preserve document order to keep selection deterministic.
    """
    return [
        obj for obj in objects
        if getattr(obj, "PatternType", "") == "PatternPiece"
    ]

def seam_visual_markers(points_a, points_b):
    """Return deterministic direction/notch/correspondence marker geometry data."""
    if len(points_a) != len(points_b) or len(points_a) < 2:
        raise ValueError("seam marker inputs must have equal length >= 2")
    def direction(start, end):
        dx = float(end[0]) - float(start[0])
        dy = float(end[1]) - float(start[1])
        length = (dx * dx + dy * dy) ** 0.5
        return (1.0, 0.0) if length <= 1e-12 else (dx / length, dy / length)
    mid = len(points_a) // 2
    ap, an = points_a[max(0, mid - 1)], points_a[min(len(points_a) - 1, mid + 1)]
    bp, bn = points_b[max(0, mid - 1)], points_b[min(len(points_b) - 1, mid + 1)]
    ax, ay = direction(ap, an)
    bx, by = direction(bp, bn)
    return {
        "correspondence": tuple((tuple(float(v) for v in a), tuple(float(v) for v in b)) for a, b in zip(points_a, points_b)),
        "direction_A": (tuple(float(v) for v in an), (ax, ay)),
        "direction_B": (tuple(float(v) for v in bn), (bx, by)),
        "notch_A": (tuple(float(v) for v in points_a[mid]), (-ay, ax)),
        "notch_B": (tuple(float(v) for v in points_b[mid]), (-by, bx)),
    }


def build_seam_visual_shape(piece_a, piece_b, seam, sample_count=5, world_space=False):
    """Build native presentation geometry for one semantic seam."""
    import FreeCAD as App
    import Part
    from freecad_cloth.sewing.SewingObjects import _edge_samples, _resolved_edge
    a = _edge_samples(piece_a, _resolved_edge(piece_a, seam, "A"),
                      float(getattr(seam, "StartA", 0.0)), float(getattr(seam, "EndA", 1.0)),
                      int(sample_count), z=0.4, transform_to_world=not world_space)
    b = _edge_samples(piece_b, _resolved_edge(piece_b, seam, "B"),
                      float(getattr(seam, "StartB", 0.0)), float(getattr(seam, "EndB", 1.0)),
                      int(sample_count), z=0.4, transform_to_world=not world_space)
    if bool(getattr(seam, "ReversedB", False)):
        b.reverse()
    if world_space:
        placement_a = getattr(piece_a, "Placement", None)
        placement_b = getattr(piece_b, "Placement", None)
        if placement_a is not None:
            a = [placement_a.multVec(point) for point in a]
        if placement_b is not None:
            b = [placement_b.multVec(point) for point in b]

    def distinct(points, tolerance=1e-9):
        result = []
        for point in points:
            if not result:
                result.append(point)
                continue
            dx = point.x - result[-1].x
            dy = point.y - result[-1].y
            dz = point.z - result[-1].z
            if (dx * dx + dy * dy + dz * dz) > tolerance * tolerance:
                result.append(point)
        return result

    a_distinct = distinct(a)
    b_distinct = distinct(b)
    shapes = []
    if len(a_distinct) >= 2:
        shapes.append(Part.makePolygon(a_distinct))
    if len(b_distinct) >= 2:
        shapes.append(Part.makePolygon(b_distinct))
    for pa, pb in zip(a, b):
        dx = pb.x - pa.x
        dy = pb.y - pa.y
        dz = pb.z - pa.z
        if (dx * dx + dy * dy + dz * dz) > 1e-18:
            shapes.append(Part.makeLine(pa, pb))
    for points in (a_distinct, b_distinct):
        if len(points) < 2:
            continue
        mid = len(points) // 2
        prev, nxt = points[max(0, mid - 1)], points[min(len(points) - 1, mid + 1)]
        dx, dy = nxt.x - prev.x, nxt.y - prev.y
        length = (dx * dx + dy * dy) ** 0.5
        ux, uy = dx / length, dy / length
        tip = points[mid]
        arrow_len = min(6.0, max(1.0, length * 0.3))
        base = App.Vector(tip.x - ux * arrow_len, tip.y - uy * arrow_len, tip.z)
        left = App.Vector(base.x + uy * arrow_len * 0.6, base.y - ux * arrow_len * 0.6, tip.z)
        right = App.Vector(base.x - uy * arrow_len * 0.6, base.y + ux * arrow_len * 0.6, tip.z)
        shapes.extend((Part.makeLine(tip, left), Part.makeLine(tip, right)))
        nx, ny = -uy, ux
        notch_len = min(4.0, max(1.0, length * 0.2))
        na = App.Vector(tip.x - nx * notch_len, tip.y - ny * notch_len, tip.z)
        nb = App.Vector(tip.x + nx * notch_len, tip.y + ny * notch_len, tip.z)
        shapes.append(Part.makeLine(na, nb))
    return Part.makeCompound(shapes)
