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



# Canonical ArrangementPoint serialization:
# name|x,y,z|wrap|rotation|symmetry
ARRANGEMENT_POINT_DEFAULT_WRAP = "front"
ARRANGEMENT_POINT_DEFAULT_ROTATION = 0.0
ARRANGEMENT_POINT_DEFAULT_SYMMETRY = ""
def arrangement_points_from_landmarks(landmarks):
    """Return canonical five-field arrangement points from local landmarks."""
    by_name = {}
    for record in landmarks or ():
        try:
            name, coords = str(record).split("|", 1)
        except ValueError:
            continue
        if name in ARRANGEMENT_POINT_NAMES:
            by_name[name] = "%s|%s|%s|%.12g|%s" % (
                name,
                coords,
                ARRANGEMENT_POINT_DEFAULT_WRAP,
                ARRANGEMENT_POINT_DEFAULT_ROTATION,
                ARRANGEMENT_POINT_DEFAULT_SYMMETRY,
            )
    return [by_name[name] for name in ARRANGEMENT_POINT_NAMES if name in by_name]


def arrangement_point_map(records):
    """Return name -> local coordinate strings from canonical or legacy records."""
    result = {}
    for record in records or ():
        parts = str(record).split("|")
        if len(parts) not in (2, 5):
            continue
        name, coords = parts[0], parts[1]
        if name in ARRANGEMENT_POINT_NAMES:
            result[name] = coords
    return result
