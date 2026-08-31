"""Solver-neutral arrangement-point metadata for the Cloth mannequin.

Arrangement points are persistent fitting metadata, not solver state. They are
stored in the mannequin's local coordinate system so normal FreeCAD Placement
continues to own world-space positioning.
"""

ARRANGEMENT_POINT_NAMES = (
    "neck", "chest", "waist", "hip",
    "shoulder_left", "shoulder_right", "knee_left", "knee_right",
)


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
