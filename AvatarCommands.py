"""FreeCAD-facing parametric avatar commands for Cloth Sewing."""
from AvatarModel import AvatarParameters, DEFAULT_MEASUREMENTS


def _avatar(doc):
    return next((o for o in doc.Objects if getattr(o, "AvatarType", "") == "ClothAvatar"), None)


def _set_prop(obj, kind, name, group, value):
    if not hasattr(obj, name):
        obj.addProperty(kind, name, group)
    setattr(obj, name, value)


def _parameters(obj):
    return AvatarParameters({
        "height": obj.Height, "chest": obj.Chest, "waist": obj.Waist,
        "hip": obj.Hip, "shoulder": obj.Shoulder,
    }, float(obj.SkinOffset), str(obj.PosePreset))


def _rebuild(obj):
    import FreeCAD as App
    import Part

    p = _parameters(obj)
    h = p.measurement("height")
    pi = 3.141592653589793
    chest_r = p.measurement("chest") / (2.0 * pi) + p.skin_offset
    waist_r = p.measurement("waist") / (2.0 * pi) + p.skin_offset
    hip_r = p.measurement("hip") / (2.0 * pi) + p.skin_offset
    shoulder = p.measurement("shoulder") / 2.0 + p.skin_offset
    torso_h = h * 0.55
    hip_h = h * 0.20
    neck_h = h * 0.08
    leg_h = h * 0.45
    leg_r = max(28.0, h * 0.028) + p.skin_offset
    arm_r = max(22.0, h * 0.024) + p.skin_offset

    torso = Part.makeCone(waist_r, chest_r, torso_h, App.Vector(0, 0, leg_h))
    pelvis = Part.makeCone(hip_r, waist_r, hip_h, App.Vector(0, 0, leg_h - hip_h * 0.35))
    neck = Part.makeCylinder(max(35.0, waist_r * 0.22), neck_h,
                             App.Vector(0, 0, leg_h + torso_h))
    head_r = max(65.0, h * 0.055) + p.skin_offset
    head = Part.makeSphere(head_r, App.Vector(0, 0, leg_h + torso_h + neck_h + head_r * 0.8))

    leg_x = max(45.0, hip_r * 0.42)
    left_leg = Part.makeCylinder(leg_r, leg_h, App.Vector(-leg_x, 0, 0))
    right_leg = Part.makeCylinder(leg_r, leg_h, App.Vector(leg_x, 0, 0))
    arm_h = torso_h * 0.78
    arm_z = leg_h + torso_h * 0.86
    left_arm = Part.makeCylinder(arm_r, arm_h, App.Vector(-shoulder, 0, arm_z))
    right_arm = Part.makeCylinder(arm_r, arm_h, App.Vector(shoulder, 0, arm_z))
    if p.pose == "sewing":
        left_arm.rotate(App.Vector(-shoulder, 0, arm_z), App.Vector(0, 1, 0), -12.0)
        right_arm.rotate(App.Vector(shoulder, 0, arm_z), App.Vector(0, 1, 0), 12.0)

    shape = torso
    for part in (pelvis, neck, head, left_leg, right_leg, left_arm, right_arm):
        shape = shape.fuse(part)
    obj.Shape = shape
    obj.AvatarStatus = "Valid"
    obj.ParametersJSON = p.to_json()


def create_avatar():
    import FreeCAD as App
    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    obj = _avatar(doc)
    if obj is None:
        obj = doc.addObject("Part::Feature", "ClothAvatar")
        obj.Label = "Cloth Avatar"
        _set_prop(obj, "App::PropertyString", "AvatarType", "Avatar", "ClothAvatar")
        _set_prop(obj, "App::PropertyString", "SchemaVersion", "Avatar", "1")
        for name, value in DEFAULT_MEASUREMENTS.items():
            _set_prop(obj, "App::PropertyLength", name.title(), "Measurements", value)
        _set_prop(obj, "App::PropertyLength", "SkinOffset", "Display", 0.0)
        _set_prop(obj, "App::PropertyEnumeration", "PosePreset", "Pose",
                  ["standing", "sewing", "sitting"])
        obj.PosePreset = "standing"
        _set_prop(obj, "App::PropertyString", "AvatarStatus", "Avatar", "Unbuilt")
        _set_prop(obj, "App::PropertyString", "ParametersJSON", "Avatar", "")
    _rebuild(obj)
    doc.recompute()
    return obj


def rebuild_avatar():
    import FreeCAD as App
    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before rebuilding the avatar")
    obj = _avatar(doc)
    if obj is None:
        raise ValueError("create a Cloth Avatar first")
    _rebuild(obj)
    doc.recompute()
    return obj


def set_avatar_measurements(height=None, chest=None, waist=None, hip=None, shoulder=None):
    import FreeCAD as App
    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before changing avatar measurements")
    obj = _avatar(doc) or create_avatar()
    for name, value in (("Height", height), ("Chest", chest), ("Waist", waist),
                        ("Hip", hip), ("Shoulder", shoulder)):
        if value is not None:
            setattr(obj, name, float(value))
    return rebuild_avatar()


def set_avatar_pose(pose):
    import FreeCAD as App
    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before changing avatar pose")
    obj = _avatar(doc) or create_avatar()
    if pose not in ("standing", "sewing", "sitting"):
        raise ValueError("unsupported avatar pose: %s" % pose)
    obj.PosePreset = pose
    return rebuild_avatar()


def set_avatar_skin_offset(offset):
    import FreeCAD as App
    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before changing avatar offset")
    obj = _avatar(doc) or create_avatar()
    if float(offset) < 0:
        raise ValueError("skin offset must not be negative")
    obj.SkinOffset = float(offset)
    return rebuild_avatar()


COMMANDS = [
    "ClothFitting_CreateAvatar", "ClothFitting_RebuildAvatar",
    "ClothFitting_SetAvatarMeasurements", "ClothFitting_SetAvatarPose",
    "ClothFitting_SetAvatarSkinOffset",
]
_HANDLERS = {
    "ClothFitting_CreateAvatar": create_avatar,
    "ClothFitting_RebuildAvatar": rebuild_avatar,
    "ClothFitting_SetAvatarMeasurements": lambda: set_avatar_measurements(
        height=1700, chest=900, waist=760, hip=960, shoulder=420),
    "ClothFitting_SetAvatarPose": lambda: set_avatar_pose("sewing"),
    "ClothFitting_SetAvatarSkinOffset": lambda: set_avatar_skin_offset(5.0),
}

try:
    import FreeCADGui as Gui
    from CommandAdapter import register_commands
    register_commands(Gui, _HANDLERS)
except (ImportError, AttributeError):
    pass
