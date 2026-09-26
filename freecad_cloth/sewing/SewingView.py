"""Small, FreeCAD-independent helpers for Sewing workbench views."""
from colorsys import hsv_to_rgb
from hashlib import sha512


_SEAM_COLOR_SATURATION = 0.78
_SEAM_COLOR_VALUE = 0.92
_SEAM_COLOR_HASH_SCALE = float(1 << 64)


def _seam_color_for_id(seam_id):
    identity = str(seam_id).strip()
    if not identity:
        raise ValueError("seam identity must not be empty")
    digest = sha512(identity.encode("utf-8")).digest()
    hue = int.from_bytes(digest[44:52], "big") / _SEAM_COLOR_HASH_SCALE
    rgb = hsv_to_rgb(hue, _SEAM_COLOR_SATURATION, _SEAM_COLOR_VALUE)
    return tuple(round(channel, 6) for channel in rgb)


def seam_color_map(seam_ids):
    """Return deterministic seam colors keyed only by canonical seam identity."""
    ids = sorted({str(seam_id).strip() for seam_id in seam_ids if str(seam_id).strip()})
    return {seam_id: _seam_color_for_id(seam_id) for seam_id in ids}


def _presentation_seam_id(obj):
    direct = str(getattr(obj, "SeamId", "")).strip()
    if direct:
        return direct
    if str(getattr(obj, "SewingType", "")).strip() == "SewingOperation":
        seam = getattr(obj, "Seam", None)
        linked = str(getattr(seam, "SeamId", "")).strip() if seam is not None else ""
        if linked:
            return linked
    return ""


def apply_seam_colors(objects):
    """Apply one deterministic line color to every user-facing seam surface."""
    presentations = []
    seam_ids = []
    for obj in objects:
        seam_id = _presentation_seam_id(obj)
        if not seam_id:
            continue
        presentations.append((obj, seam_id))
        seam_ids.append(seam_id)
    colors = seam_color_map(seam_ids)
    for obj, seam_id in presentations:
        view = getattr(obj, "ViewObject", None)
        color = colors.get(seam_id)
        if view is not None and color is not None:
            view.LineColor = color
    return colors


def pattern_pieces_for_2d(objects):
    """Return PatternPiece objects participating in the sewing 2D focus."""
    return [obj for obj in objects if getattr(obj, "PatternType", "") == "PatternPiece"]


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
    ax, ay = direction(ap, an); bx, by = direction(bp, bn)
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
    a = _edge_samples(piece_a, _resolved_edge(piece_a, seam, "A"), float(getattr(seam, "StartA", 0.0)), float(getattr(seam, "EndA", 1.0)), int(sample_count), z=0.4, transform_to_world=not world_space)
    b = _edge_samples(piece_b, _resolved_edge(piece_b, seam, "B"), float(getattr(seam, "StartB", 0.0)), float(getattr(seam, "EndB", 1.0)), int(sample_count), z=0.4, transform_to_world=not world_space)
    if bool(getattr(seam, "ReversedB", False)): b.reverse()
    if world_space:
        placement_a = getattr(piece_a, "Placement", None); placement_b = getattr(piece_b, "Placement", None)
        if placement_a is not None: a = [placement_a.multVec(point) for point in a]
        if placement_b is not None: b = [placement_b.multVec(point) for point in b]
    def distinct(points, tolerance=1e-9):
        result=[]
        for point in points:
            if not result: result.append(point); continue
            dx=point.x-result[-1].x; dy=point.y-result[-1].y; dz=point.z-result[-1].z
            if (dx*dx+dy*dy+dz*dz) > tolerance*tolerance: result.append(point)
        return result
    a_distinct=distinct(a); b_distinct=distinct(b); shapes=[]
    if len(a_distinct)>=2: shapes.append(Part.makePolygon(a_distinct))
    if len(b_distinct)>=2: shapes.append(Part.makePolygon(b_distinct))
    for pa,pb in zip(a,b):
        dx=pb.x-pa.x; dy=pb.y-pa.y; dz=pb.z-pa.z
        if (dx*dx+dy*dy+dz*dz)>1e-18: shapes.append(Part.makeLine(pa,pb))
    for points in (a_distinct,b_distinct):
        if len(points)<2: continue
        mid=len(points)//2; prev,nxt=points[max(0,mid-1)],points[min(len(points)-1,mid+1)]
        dx,dy=nxt.x-prev.x,nxt.y-prev.y; length=(dx*dx+dy*dy)**0.5; ux,uy=dx/length,dy/length
        tip=points[mid]; arrow_len=min(6.0,max(1.0,length*0.3))
        base=App.Vector(tip.x-ux*arrow_len,tip.y-uy*arrow_len,tip.z)
        left=App.Vector(base.x+uy*arrow_len*0.6,base.y-ux*arrow_len*0.6,tip.z)
        right=App.Vector(base.x-uy*arrow_len*0.6,base.y+ux*arrow_len*0.6,tip.z)
        shapes.extend((Part.makeLine(tip,left),Part.makeLine(tip,right)))
        nx,ny=-uy,ux; notch_len=min(4.0,max(1.0,length*0.2))
        na=App.Vector(tip.x-nx*notch_len,tip.y-ny*notch_len,tip.z); nb=App.Vector(tip.x+nx*notch_len,tip.y+ny*notch_len,tip.z)
        shapes.append(Part.makeLine(na,nb))
    return Part.makeCompound(shapes)
