"""Solver-neutral arrangement-point metadata for the Cloth mannequin.

Arrangement points are persistent fitting metadata, not solver state. They are
stored in the mannequin's local coordinate system so normal FreeCAD Placement
continues to own world-space positioning. This provides the persistent fitting
anchor foundation needed by later CLO-like garment placement interactions.
"""

ARRANGEMENT_POINT_NAMES = (
    "neck", "chest", "waist", "hip",
    "shoulder_left", "shoulder_right", "knee_left", "knee_right",
)


def wrapped_panel_angles(front_y, back_y, target_y, seam_height, max_inward_cos=0.35):
    """Return front/back X-axis tilt angles that wrap a flat panel seam around an avatar.
    
    The returned angles are measured in degrees. A front panel uses an angle above
    90° so its shoulder edge leans inward; the back panel uses the mirrored angle
    below 90°. The helper is solver-neutral and only depends on the authored
    target-side geometry, making the initial arrangement deterministic and
    reversible before any cloth constraints are solved.
    """
    seam_height = float(seam_height)
    if seam_height <= 0.0:
        raise ValueError("seam height must be positive")
    limit = max(0.0, min(0.999, float(max_inward_cos)))
    front_cos = max(-limit, min(limit, (float(target_y) - float(front_y)) / seam_height))
    back_cos = max(-limit, min(limit, (float(target_y) - float(back_y)) / seam_height))
    from math import acos, degrees
    return degrees(acos(front_cos)), degrees(acos(back_cos))


def arrangement_points_from_landmarks(landmarks):
    """Return stable ``name|x,y,z`` arrangement points from landmark records."""
    by_name = {}
    for record in landmarks or ():
        try:
            name, coords = str(record).split("|", 1)
        except ValueError:
            continue
        if name in ARRANGEMENT_POINT_NAMES:
            by_name[name] = "%s|%s" % (name, coords)
    return [by_name[name] for name in ARRANGEMENT_POINT_NAMES if name in by_name]


def arrangement_point_map(records):
    """Return arrangement records as a name -> coordinate-string mapping."""
    result = {}
    for record in records or ():
        try:
            name, coords = str(record).split("|", 1)
        except ValueError:
            continue
        if name in ARRANGEMENT_POINT_NAMES:
            result[name] = coords
    return result
