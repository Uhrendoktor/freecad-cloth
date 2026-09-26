"""Solver-neutral arrangement-point metadata for the Cloth mannequin.

Arrangement points are persistent fitting metadata, not solver state. They are
stored in the mannequin's local coordinate system so normal FreeCAD Placement
continues to own world-space positioning. This provides the persistent fitting
anchor foundation needed by later CLO-like garment placement interactions.
"""

ARRANGEMENT_POINT_NAMES = (
    "neck", "chest", "underbust", "waist", "high_hip", "hip",
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


def _parse_coordinates(records):
    result = {}
    for name, coords in arrangement_point_map(records).items():
        try:
            values = tuple(float(value) for value in str(coords).split(","))
        except (TypeError, ValueError):
            continue
        if len(values) == 3:
            result[name] = values
    return result


def torso_arrangement_frame(landmarks, vertices, surface_padding=0.0):
    """Derive a deterministic torso fitting frame from landmarks and surface."""
    points = _parse_coordinates(landmarks)
    required = ("shoulder_left", "shoulder_right", "high_hip")
    missing = [name for name in required if name not in points]
    if missing:
        raise ValueError("avatar arrangement landmarks missing: %s" % ", ".join(missing))
    if not vertices:
        raise ValueError("avatar arrangement requires target surface vertices")
    left = points["shoulder_left"]
    right = points["shoulder_right"]
    low = points["high_hip"]
    center_x = (left[0] + right[0]) / 2.0
    shoulder_half = max(1.0, abs(right[0] - left[0]) / 2.0)
    top_z = (left[2] + right[2]) / 2.0
    low_z = float(low[2])
    z_margin = max(20.0, 0.05 * max(1.0, top_z - low_z))
    x_limit = shoulder_half * 1.15
    torso = [
        (float(v[0]), float(v[1]), float(v[2]))
        for v in vertices
        if low_z - z_margin <= float(v[2]) <= top_z + z_margin
        and abs(float(v[0]) - center_x) <= x_limit
    ]
    if len(torso) < 8:
        torso = [(float(v[0]), float(v[1]), float(v[2])) for v in vertices]
    front_y = max(v[1] for v in torso) + float(surface_padding)
    back_y = min(v[1] for v in torso) - float(surface_padding)
    if front_y <= back_y:
        raise ValueError("avatar arrangement surface has invalid front/back depth")
    return {
        "center_x": float(center_x),
        "top_z": float(top_z),
        "low_z": float(low_z),
        "shoulder_half": float(shoulder_half),
        "front_y": float(front_y),
        "back_y": float(back_y),
    }


def _world_vertices(avatar):
    """Return avatar mesh vertices in world coordinates."""
    mesh = getattr(avatar, "Mesh", None)
    topology = getattr(mesh, "Topology", None)
    if topology is None:
        raise ValueError("avatar mesh topology is unavailable")
    vertices, _triangles = topology
    placement = getattr(avatar, "Placement", None)
    transform = getattr(placement, "multVec", None)
    points = []
    for point in vertices:
        values = (float(point.x), float(point.y), float(point.z))
        if transform is not None:
            world = transform(point)
            values = (float(world.x), float(world.y), float(world.z))
        points.append(values)
    return tuple(points)


def _world_landmarks(avatar):
    """Return persisted avatar arrangement records transformed to world space."""
    import FreeCAD as App
    placement = getattr(avatar, "Placement", None)
    transform = getattr(placement, "multVec", None)
    output = []
    records = getattr(avatar, "ArrangementPoints", None) or getattr(avatar, "Landmarks", ())
    for record in arrangement_points_from_landmarks(records):
        name, coords = record.split("|", 1)
        point = App.Vector(*(float(value) for value in coords.split(",")))
        if transform is not None:
            point = transform(point)
        output.append("%s|%.12g,%.12g,%.12g" % (name, point.x, point.y, point.z))
    return output


def arrange_two_panel_garment(front_piece, back_piece, avatar, surface_padding=None):
    """Place a front/back panel pair on the avatar before simulation.

    This is arrangement metadata/placement only; no solver pins are added.
    """
    import FreeCAD as App
    records = _world_landmarks(avatar)
    padding = float(getattr(avatar, "SkinOffset", 0.0) if surface_padding is None else surface_padding)
    frame = torso_arrangement_frame(records, _world_vertices(avatar), padding)
    rotation = App.Rotation(App.Vector(1, 0, 0), 90.0)
    placements = {}
    for label, piece, side in (("front", front_piece, "front"), ("back", back_piece, "back")):
        width = float(getattr(piece, "Width", 0.0))
        height = float(getattr(piece, "Height", 0.0))
        if width <= 0.0 or height <= 0.0:
            shape_box = getattr(getattr(piece, "Shape", None), "BoundBox", None)
            width = float(getattr(shape_box, "XLength", 0.0))
            height = float(getattr(shape_box, "YLength", 0.0))
        if width <= 0.0 or height <= 0.0:
            raise ValueError("pattern piece has no usable 2D dimensions")
        base = App.Vector(frame["center_x"] - width / 2.0,
                          frame["front_y"] if side == "front" else frame["back_y"],
                          frame["top_z"] - height)
        placement = App.Placement(base, rotation)
        piece.Placement = placement
        sketch = getattr(piece, "Sketch", None)
        if sketch is not None:
            sketch.Placement = placement
        placements[label] = {
            "x": float(base.x), "y": float(base.y), "z": float(base.z),
            "width": width, "height": height,
        }
    return {"profile": "avatar-torso-surface-v1", "frame": frame, "placements": placements}
