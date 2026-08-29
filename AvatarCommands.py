"""FreeCAD-facing parametric human mannequin commands."""
from AvatarModel import AvatarParameters, DEFAULT_MEASUREMENTS, Pose


def _avatar(doc):
    return next((o for o in doc.Objects if getattr(o, "AvatarType", "") == "ClothAvatar"), None)


def _set_prop(obj, kind, name, group, value):
    if not hasattr(obj, name):
        obj.addProperty(kind, name, group)
    setattr(obj, name, value)


def _parameters(obj):
    values = {name: float(getattr(obj, name.title())) for name in DEFAULT_MEASUREMENTS}
    return AvatarParameters(values, float(obj.SkinOffset), Pose(str(obj.PosePreset)))


def _limb(base, end, radius):
    import FreeCAD as App
    import Part
    a = App.Vector(*base)
    b = App.Vector(*end)
    direction = b.sub(a)
    length = direction.Length
    if length < 1e-6:
        return Part.makeSphere(radius, a)
    return Part.makeCylinder(radius, length, a, direction)


def _rebuild(obj):
    import FreeCAD as App
    import Part
    p = _parameters(obj)
    m = p.measurements
    h = m["height"]
    pi = 3.141592653589793
    # Approximate elliptical circumferences by slightly wider-than-circular
    # radii.  This is intentionally a replaceable generator behind the avatar
    # API, not an anatomical solver.
    chest_r = m["chest"] / (2*pi) * 1.18 + p.skin_offset
    waist_r = m["waist"] / (2*pi) * 1.18 + p.skin_offset
    hip_r = m["hip"] / (2*pi) * 1.18 + p.skin_offset
    neck_r = m["neck"] / (2*pi) + p.skin_offset
    pelvis_z = m["inseam"] + 120.0
    waist_z = pelvis_z + m["back_waist"]
    chest_z = waist_z + max(90.0, m["torso"] * 0.72)
    shoulder_z = min(h - 180.0, chest_z + 150.0)
    neck_z = shoulder_z + 100.0

    pelvis = Part.makeCone(hip_r, waist_r, max(100.0, waist_z-pelvis_z), App.Vector(0, 0, pelvis_z))
    torso = Part.makeCone(waist_r, chest_r, max(100.0, chest_z-waist_z), App.Vector(0, 0, waist_z))
    shoulder = Part.makeCone(chest_r, chest_r*0.88, 150.0, App.Vector(0, 0, chest_z))
    neck = Part.makeCylinder(neck_r, 100.0, App.Vector(0, 0, shoulder_z))
    head_r = max(70.0, h * 0.055) + p.skin_offset
    head = Part.makeSphere(head_r, App.Vector(0, 0, neck_z + 70.0))

    leg_radius = max(28.0, m["thigh"]/(2*pi)) + p.skin_offset
    calf_radius = max(25.0, m["calf"]/(2*pi)) + p.skin_offset
    knee_z = max(300.0, m["ankle"] + m["inseam"]*0.52)
    ankle_z = m["ankle"] / 2.0
    leg_x = max(55.0, hip_r*0.42)
    feet = []
    legs = []
    for side in (-1.0, 1.0):
        x = side * leg_x
        legs.extend((_limb((x, 0, pelvis_z), (x, 0, knee_z), leg_radius),
                     _limb((x, 0, knee_z), (x, 0, ankle_z+55), calf_radius)))
        feet.append(Part.makeSphere(max(35.0, m["ankle"]/(2*pi)), App.Vector(x, 35.0, ankle_z)))

    shoulder_half = m["shoulder"] / 2.0
    arm_radius = max(22.0, m["upper_arm"]/(2*pi)) + p.skin_offset
    forearm_radius = max(20.0, m["elbow"]/(2*pi)*0.9) + p.skin_offset
    wrist_radius = max(16.0, m["wrist"]/(2*pi)) + p.skin_offset
    arm_z = shoulder_z - 15.0
    arms = []
    for side in (-1.0, 1.0):
        sx = side * shoulder_half
        abduct = 0.0 if p.pose.preset == "standing" else side * 45.0
        ex = side * (shoulder_half + 125.0)
        ez = arm_z - 35.0
        wx = side * (shoulder_half + 245.0)
        wz = arm_z - 55.0
        if p.pose.preset == "sewing":
            abduct = side * 65.0
            ez = arm_z - 10.0
            wz = arm_z + 20.0
        arms.extend((_limb((sx, 0, arm_z), (ex, abduct, ez), arm_radius),
                     _limb((ex, abduct, ez), (wx, abduct, wz), forearm_radius),
                     Part.makeSphere(wrist_radius*1.25, App.Vector(wx, abduct, wz))))

    # Rounded joints make the silhouette substantially more human than isolated
    # cylinders while keeping the model inexpensive for repeated recomputes.
    joints = []
    for side in (-1.0, 1.0):
        x = side * leg_x
        joints.append(Part.makeSphere(leg_radius*1.05, App.Vector(x, 0, knee_z)))
        joints.append(Part.makeSphere(arm_radius*1.1, App.Vector(side*shoulder_half, 0, arm_z)))

    shape = pelvis.fuse(torso).fuse(shoulder).fuse(neck).fuse(head)
    for part in legs + feet + arms + joints:
        shape = shape.fuse(part)
    obj.Shape = shape
    obj.ParametersJSON = p.to_json()
    obj.AvatarStatus = "Valid"
    obj.Landmarks = [
        "neck|0,0,%.3f" % neck_z,
        "chest|0,0,%.3f" % chest_z,
        "waist|0,0,%.3f" % waist_z,
        "hip|0,0,%.3f" % pelvis_z,
        "shoulder_left|%.3f,0,%.3f" % (-shoulder_half, arm_z),
        "shoulder_right|%.3f,0,%.3f" % (shoulder_half, arm_z),
        "knee_left|%.3f,0,%.3f" % (-leg_x, knee_z),
        "knee_right|%.3f,0,%.3f" % (leg_x, knee_z),
    ]
    obj.Document.recompute()
    return obj


def create_avatar():
    import FreeCAD as App
    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    obj = _avatar(doc)
    if obj is None:
        obj = doc.addObject("Part::Feature", "ClothAvatar")
        obj.Label = "Cloth Human Mannequin"
        _set_prop(obj, "App::PropertyString", "AvatarType", "Avatar", "ClothAvatar")
        _set_prop(obj, "App::PropertyString", "SchemaVersion", "Avatar", "1")
        for name, value in DEFAULT_MEASUREMENTS.items():
            _set_prop(obj, "App::PropertyLength", name.title(), "Measurements", value)
        _set_prop(obj, "App::PropertyLength", "SkinOffset", "Collision", 3.0)
        _set_prop(obj, "App::PropertyEnumeration", "PosePreset", "Pose", ["standing", "sewing", "sitting"])
        obj.PosePreset = "standing"
        _set_prop(obj, "App::PropertyString", "AvatarStatus", "Avatar", "Unbuilt")
        _set_prop(obj, "App::PropertyString", "ParametersJSON", "Avatar", "")
        _set_prop(obj, "App::PropertyStringList", "Landmarks", "Measurements", [])
    return _rebuild(obj)


def rebuild_avatar():
    import FreeCAD as App
    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before rebuilding the avatar")
    obj = _avatar(doc)
    if obj is None:
        raise ValueError("create a Cloth Avatar first")
    return _rebuild(obj)


def set_avatar_measurements(**changes):
    import FreeCAD as App
    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before changing avatar measurements")
    obj = _avatar(doc) or create_avatar()
    for name, value in changes.items():
        property_name = str(name).title()
        if property_name not in [k.title() for k in DEFAULT_MEASUREMENTS]:
            raise ValueError("unknown avatar measurement: %s" % name)
        setattr(obj, property_name, float(value))
    return _rebuild(obj)


def set_avatar_pose(pose):
    import FreeCAD as App
    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before changing avatar pose")
    obj = _avatar(doc) or create_avatar()
    Pose(str(pose)).validate()
    obj.PosePreset = str(pose)
    return _rebuild(obj)


def set_avatar_skin_offset(offset):
    import FreeCAD as App
    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before changing avatar offset")
    obj = _avatar(doc) or create_avatar()
    obj.SkinOffset = float(offset)
    return _rebuild(obj)


def avatar_measurement(name):
    import FreeCAD as App
    doc = App.ActiveDocument
    if doc is None or _avatar(doc) is None:
        raise ValueError("create a Cloth Avatar first")
    return _parameters(_avatar(doc)).measurement(str(name))


COMMANDS = [
    "ClothFitting_CreateAvatar", "ClothFitting_RebuildAvatar",
    "ClothFitting_SetAvatarMeasurements", "ClothFitting_SetAvatarPose",
    "ClothFitting_SetAvatarSkinOffset",
]
_HANDLERS = {
    "ClothFitting_CreateAvatar": create_avatar,
    "ClothFitting_RebuildAvatar": rebuild_avatar,
    "ClothFitting_SetAvatarMeasurements": lambda: set_avatar_measurements(height=1750, chest=980, waist=820, hip=1020),
    "ClothFitting_SetAvatarPose": lambda: set_avatar_pose("sewing"),
    "ClothFitting_SetAvatarSkinOffset": lambda: set_avatar_skin_offset(5.0),
}

try:
    import FreeCADGui as Gui
    from CommandAdapter import register_commands
    register_commands(Gui, _HANDLERS)
except (ImportError, AttributeError):
    pass
