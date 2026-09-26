"""Deterministic target-relative rigid garment placement.

The placement layer consumes the persistent DrapeTarget collision surface but
does not alter solver constraints. It translates authored pattern pieces toward
the nearest valid target surface with a bounded outward clearance and rolls back
transactionally when the resulting piece boundary is not clear.
"""

from math import sqrt
from typing import Iterable, Tuple

_EPSILON = 1.0e-9


def _sub(a, b):
    return (float(a[0]) - float(b[0]), float(a[1]) - float(b[1]), float(a[2]) - float(b[2]))


def _add(a, b):
    return (float(a[0]) + float(b[0]), float(a[1]) + float(b[1]), float(a[2]) + float(b[2]))


def _scale(a, scalar):
    return (float(a[0]) * float(scalar), float(a[1]) * float(scalar), float(a[2]) * float(scalar))


def _dot(a, b):
    return float(a[0]) * float(b[0]) + float(a[1]) * float(b[1]) + float(a[2]) * float(b[2])


def _cross(a, b):
    return (
        float(a[1]) * float(b[2]) - float(a[2]) * float(b[1]),
        float(a[2]) * float(b[0]) - float(a[0]) * float(b[2]),
        float(a[0]) * float(b[1]) - float(a[1]) * float(b[0]),
    )


def _norm(a):
    return sqrt(max(0.0, _dot(a, a)))


def _unit(a):
    length = _norm(a)
    if length <= _EPSILON:
        return None
    return _scale(a, 1.0 / length)


def _closest_point_on_triangle(point, a, b, c):
    """Return the closest point on a triangle using standard region tests."""
    ab = _sub(b, a)
    ac = _sub(c, a)
    ap = _sub(point, a)
    d1 = _dot(ab, ap)
    d2 = _dot(ac, ap)
    if d1 <= 0.0 and d2 <= 0.0:
        return a
    bp = _sub(point, b)
    d3 = _dot(ab, bp)
    d4 = _dot(ac, bp)
    if d3 >= 0.0 and d4 <= d3:
        return b
    vc = d1 * d4 - d3 * d2
    if vc <= 0.0 and d1 >= 0.0 and d3 <= 0.0:
        denominator = d1 - d3
        return _add(a, _scale(ab, d1 / denominator)) if abs(denominator) > _EPSILON else a
    cp = _sub(point, c)
    d5 = _dot(ab, cp)
    d6 = _dot(ac, cp)
    if d6 >= 0.0 and d5 <= d6:
        return c
    vb = d5 * d2 - d1 * d6
    if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
        denominator = d2 - d6
        return _add(a, _scale(ac, d2 / denominator)) if abs(denominator) > _EPSILON else a
    va = d3 * d6 - d5 * d4
    if va <= 0.0 and (d4 - d3) >= 0.0 and (d5 - d6) >= 0.0:
        bc = _sub(c, b)
        denominator = (d4 - d3) + (d5 - d6)
        return _add(b, _scale(bc, (d4 - d3) / denominator)) if abs(denominator) > _EPSILON else b
    denominator = va + vb + vc
    if abs(denominator) <= _EPSILON:
        return a
    inv = 1.0 / denominator
    return _add(a, _add(_scale(ab, vb * inv), _scale(ac, vc * inv)))


def _triangle_normal(a, b, c, surface_center):
    normal = _unit(_cross(_sub(b, a), _sub(c, a)))
    if normal is None:
        return None
    tri_center = _scale(_add(_add(a, b), c), 1.0 / 3.0)
    outward_hint = _sub(tri_center, surface_center)
    if _norm(outward_hint) > _EPSILON and _dot(normal, outward_hint) < 0.0:
        normal = _scale(normal, -1.0)
    return normal


def closest_surface_anchor(point, surface):
    """Return the nearest surface point and deterministic outward normal."""
    surface.validate()
    best = None
    center = surface.center
    for triangle_index, (ia, ib, ic) in enumerate(surface.triangles):
        a, b, c = surface.vertices[ia], surface.vertices[ib], surface.vertices[ic]
        normal = _triangle_normal(a, b, c, center)
        if normal is None:
            continue
        closest = _closest_point_on_triangle(point, a, b, c)
        delta = _sub(point, closest)
        distance_squared = _dot(delta, delta)
        candidate = (distance_squared, triangle_index, closest, normal)
        if best is None or candidate[:2] < best[:2]:
            best = candidate
    if best is None:
        raise ValueError("drape target surface has no usable non-degenerate triangles")
    return {
        "distance": sqrt(max(0.0, best[0])),
        "point": tuple(best[2]),
        "normal": tuple(best[3]),
        "triangle_index": int(best[1]),
    }


def signed_clearance(points: Iterable[Tuple[float, float, float]], surface) -> float:
    """Return minimum outward signed distance from points to the target."""
    minimum = float("inf")
    for point in points:
        anchor = closest_surface_anchor(point, surface)
        signed = _dot(_sub(point, anchor["point"]), anchor["normal"]) - float(surface.thickness)
        minimum = min(minimum, signed)
    return 0.0 if minimum == float("inf") else float(minimum)


def solve_target_translation(anchor, surface, clearance=2.0, max_translation=250.0):
    """Return a bounded translation that moves an anchor outside the target."""
    clearance = float(clearance)
    max_translation = float(max_translation)
    if clearance < 0.0:
        raise ValueError("placement clearance must not be negative")
    if max_translation <= 0.0:
        raise ValueError("maximum placement translation must be positive")
    match = closest_surface_anchor(anchor, surface)
    desired = _add(match["point"], _scale(match["normal"], clearance + float(surface.thickness)))
    translation = _sub(desired, anchor)
    distance = _norm(translation)
    if distance > max_translation + 1.0e-7:
        raise ValueError("target-relative placement exceeds maximum translation: %.3f mm" % distance)
    return tuple(translation), match


def _single_target(target):
    if target is None:
        raise ValueError("a DrapeTarget is required")
    if isinstance(target, (tuple, list, set)):
        values = tuple(target)
        if len(values) != 1:
            raise ValueError("ambiguous drape target selection")
        return values[0]
    return target


def _placement_tuple(piece):
    placement = getattr(piece, "Placement", None)
    if placement is None:
        raise ValueError("pattern piece has no FreeCAD Placement")
    base = placement.Base
    rotation = placement.Rotation
    axis = rotation.Axis
    return (
        (float(base.x), float(base.y), float(base.z)),
        (float(rotation.Angle), float(axis.x), float(axis.y), float(axis.z)),
    )


def _restore_placements(pieces, originals):
    import FreeCAD as App
    for piece in pieces:
        base, rotation = originals[piece.Name]
        piece.Placement = App.Placement(
            App.Vector(*base),
            App.Rotation(App.Vector(rotation[1], rotation[2], rotation[3]), rotation[0]),
        )


def _persist_fitting_placements(doc, pieces):
    """Keep the existing FittingScene placement ledger aligned when present."""
    if doc is None:
        return
    scene = next(
        (obj for obj in getattr(doc, "Objects", ()) if getattr(obj, "FittingType", "") == "FittingScene"),
        None,
    )
    if scene is None:
        return
    from freecad_cloth.avatar.AvatarFitting import PiecePlacement
    entries = {
        placement.piece_id: placement
        for placement in (PiecePlacement.from_string(value) for value in getattr(scene, "PiecePlacements", ()) or ())
    }
    for piece in pieces:
        base, rotation = _placement_tuple(piece)
        entries[str(piece.PieceId)] = PiecePlacement(str(piece.PieceId), base, rotation[0])
    scene.PiecePlacements = [entries[key].to_string() for key in sorted(entries)]
    scene.FitStatus = "Target-relative arrangement applied"


def arrange_pattern_pieces_to_target(pieces, target, clearance=2.0, max_translation=250.0):
    """Place pattern pieces against the authoritative DrapeTarget surface."""
    import FreeCAD as App
    from freecad_cloth.simulation.DrapeTarget import collision_surface, target_status

    target = _single_target(target)
    status = target_status(target)
    if status["state"] != "ready":
        raise RuntimeError(status["message"])
    source = getattr(target, "SourceObject", None)
    if source is None:
        raise RuntimeError("drape target source is missing")
    surface = collision_surface(
        source,
        float(getattr(target, "CollisionDeflection", 1.0)),
        float(getattr(target, "CollisionThickness", 0.0)),
    )
    ordered = tuple(sorted(
        (piece for piece in pieces or () if getattr(piece, "PatternType", "") == "PatternPiece"),
        key=lambda item: str(getattr(item, "PieceId", "")),
    ))
    if not ordered:
        raise ValueError("at least one pattern piece is required")
    originals = {piece.Name: _placement_tuple(piece) for piece in ordered}
    try:
        for piece in ordered:
            shape = getattr(piece, "Shape", None)
            if shape is None or shape.isNull():
                raise ValueError("pattern piece %s has no valid shape" % piece.Name)
            box = shape.BoundBox
            local_anchor = App.Vector(
                0.5 * (float(box.XMin) + float(box.XMax)),
                0.5 * (float(box.YMin) + float(box.YMax)),
                0.5 * (float(box.ZMin) + float(box.ZMax)),
            )
            current = piece.Placement.multVec(local_anchor)
            translation, _match = solve_target_translation(
                (current.x, current.y, current.z),
                surface,
                clearance=clearance,
                max_translation=max_translation,
            )
            base = piece.Placement.Base
            rotation = piece.Placement.Rotation
            piece.Placement = App.Placement(
                App.Vector(base.x + translation[0], base.y + translation[1], base.z + translation[2]),
                rotation,
            )
        boundary_points = []
        for piece in ordered:
            for vertex in getattr(piece.Shape, "Vertexes", ()):
                point = piece.Placement.multVec(vertex.Point)
                boundary_points.append((float(point.x), float(point.y), float(point.z)))
        minimum = signed_clearance(boundary_points, surface)
        required = float(clearance)
        if minimum + 1.0e-6 < required:
            raise RuntimeError(
                "target-relative arrangement failed step-0 clearance: %.3f mm < %.3f mm" % (minimum, required)
            )
        _persist_fitting_placements(getattr(ordered[0], "Document", None), ordered)
        return {
            "placements": tuple(_placement_tuple(piece) for piece in ordered),
            "minimum_clearance": float(minimum),
            "target": str(getattr(target, "Name", "")),
            "clearance": required,
        }
    except BaseException:
        _restore_placements(ordered, originals)
        doc = getattr(ordered[0], "Document", None)
        if doc is not None:
            doc.recompute()
        raise
