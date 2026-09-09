"""FreeCAD-facing humanoid mesh avatar commands."""
from freecad_cloth.avatar.AvatarModel import AvatarParameters, DEFAULT_MEASUREMENTS, Pose, generate_mesh
from freecad_cloth.avatar.AvatarCollision import surface_from_triangles
from freecad_cloth.avatar.AvatarArrangement import arrangement_points_from_landmarks

PROPERTY_MAP = {
    "height": "Height", "neck": "Neck", "shoulder": "Shoulder",
    "chest": "Chest", "underbust": "Underbust", "waist": "Waist",
    "high_hip": "High_Hip", "hip": "Hip", "upper_arm": "Upper_Arm",
    "elbow": "Elbow", "wrist": "Wrist", "thigh": "Thigh",
    "knee": "Knee", "calf": "Calf", "ankle": "Ankle",
    "inseam": "Inseam", "torso": "Torso", "front_waist": "Front_Waist",
    "back_waist": "Back_Waist",
}
POSE_PROPERTY_MAP = {
    "left_arm_angle": "LeftArmAngle", "right_arm_angle": "RightArmAngle",
    "left_elbow_angle": "LeftElbowAngle", "right_elbow_angle": "RightElbowAngle",
}


def _avatar(doc):
    return next((o for o in doc.Objects if getattr(o, "AvatarType", "") == "ClothAvatar"), None)


def _set_prop(obj, kind, name, group, value):
    if not hasattr(obj, name):
        obj.addProperty(kind, name, group)
    setattr(obj, name, value)


def _parameters(obj):
    values = {name: float(getattr(obj, PROPERTY_MAP[name])) for name in DEFAULT_MEASUREMENTS}
    pose = Pose(str(obj.PosePreset), *(float(getattr(obj, POSE_PROPERTY_MAP[name], 12.0 if "arm" in name else 0.0)) for name in ("left_arm_angle", "right_arm_angle", "left_elbow_angle", "right_elbow_angle")))
    return AvatarParameters(values, float(obj.SkinOffset), pose)


def _mesh_shape(vertices, triangles):
    """Convert a triangle mesh to a FreeCAD Shape without primitive solids."""
    import FreeCAD as App
    import Mesh
    native = Mesh.Mesh()
    vectors = [App.Vector(*point) for point in vertices]
    for a, b, c in triangles:
        native.addFacet(vectors[a], vectors[b], vectors[c])
    try:
        import ArchCommands
        shape = ArchCommands.meshToShape(native, mark=False, fast=True, tol=0.05, flat=False, cut=False)
        if hasattr(shape, "Shape"):
            shape = shape.Shape
        if shape is not None and not shape.isNull():
            return shape
    except (ImportError, AttributeError, RuntimeError, TypeError, ValueError):
        pass
    # The fallback is still a faceted mesh surface: each face is derived from
    # the supplied humanoid topology, never a cylinder/sphere/cone primitive.
    import Part
    faces = []
    for a, b, c in triangles:
        wire = Part.makePolygon([vectors[a], vectors[b], vectors[c], vectors[a]])
        faces.append(Part.Face(wire))
    return Part.makeCompound(faces)


def _rebuild(obj):
    params = _parameters(obj)
    vertices, triangles, landmarks = generate_mesh(params)
    obj.Shape = _mesh_shape(vertices, triangles)
    obj.ParametersJSON = params.to_json()
    obj.AvatarStatus = "Valid"
    obj.AvatarMeshProvider = "makehuman-hm08"
    obj.AvatarMeshSource = "MakeHuman HM08 base mesh @ %s" % __import__("freecad_cloth.avatar.HumanoidMesh", fromlist=["MAKEHUMAN_COMMIT"]).MAKEHUMAN_COMMIT
    obj.AvatarMeshLicense = "CC0"
    obj.MeshVertexCount = len(vertices)
    obj.MeshTriangleCount = len(triangles)
    obj.Landmarks = ["%s|%s,%s,%s" % (landmark.name, landmark.position[0], landmark.position[1], landmark.position[2]) for landmark in landmarks]
    _set_prop(obj, "App::PropertyStringList", "ArrangementPoints", "Fitting", [])
    obj.ArrangementPoints = arrangement_points_from_landmarks(obj.Landmarks)
    obj.Document.recompute()
    return obj


def _ensure_collision(obj):
    from freecad_cloth.simulation.SimulationObjects import set_avatar_collision_source
    avatar = obj.Document.getObject("AvatarCollision")
    if avatar is None:
        from freecad_cloth.simulation.SimulationObjects import create_avatar_collision
        avatar = create_avatar_collision(obj.Document, obj, thickness=2.0, deflection=1.0)
    else:
        avatar = set_avatar_collision_source(next((s for s in obj.Document.Objects if getattr(s, "FittingType", "") == "FittingScene"), None) or _make_scene(obj.Document), obj, 2.0, 1.0)
    return avatar


def _ensure_drape_target(obj):
    """Attach the humanoid mesh to the same target-neutral collision API as CAD targets."""
    from freecad_cloth.simulation.DrapeTarget import assign_drape_target, create_drape_target
    target = obj.Document.getObject("DrapeTarget")
    if target is None:
        target = create_drape_target(obj.Document, target_type="Mannequin", deflection=1.0, thickness=2.0)
    assign_drape_target(target, obj, "Mannequin")
    return target


def _make_scene(doc):
    from freecad_cloth.simulation.FittingCommands import create_fitting_scene
    return create_fitting_scene()


def create_avatar():
    import FreeCAD as App
    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    obj = _avatar(doc)
    if obj is None:
        obj = doc.addObject("Part::Feature", "ClothAvatar")
        obj.Label = "Cloth Human Avatar"
        _set_prop(obj, "App::PropertyString", "AvatarType", "Avatar", "ClothAvatar")
        _set_prop(obj, "App::PropertyString", "SchemaVersion", "Avatar", "1")
        for name, value in DEFAULT_MEASUREMENTS.items():
            _set_prop(obj, "App::PropertyLength", PROPERTY_MAP[name], "Measurements", value)
        _set_prop(obj, "App::PropertyLength", "SkinOffset", "Collision", 3.0)
        _set_prop(obj, "App::PropertyEnumeration", "PosePreset", "Pose", ["standing", "sewing", "sitting"])
        obj.PosePreset = "standing"
        for name, prop in POSE_PROPERTY_MAP.items():
            _set_prop(obj, "App::PropertyAngle", prop, "Pose", 12.0 if "arm" in name else 0.0)
        _set_prop(obj, "App::PropertyString", "AvatarStatus", "Avatar", "Unbuilt")
        _set_prop(obj, "App::PropertyString", "ParametersJSON", "Avatar", "")
        _set_prop(obj, "App::PropertyStringList", "Landmarks", "Measurements", [])
        _set_prop(obj, "App::PropertyStringList", "ArrangementPoints", "Fitting", [])
        _set_prop(obj, "App::PropertyString", "AvatarMeshProvider", "Avatar", "")
        _set_prop(obj, "App::PropertyString", "AvatarMeshSource", "Avatar", "")
        _set_prop(obj, "App::PropertyString", "AvatarMeshLicense", "Avatar", "")
        _set_prop(obj, "App::PropertyInteger", "MeshVertexCount", "Avatar", 0)
        _set_prop(obj, "App::PropertyInteger", "MeshTriangleCount", "Avatar", 0)
        _set_prop(obj, "App::PropertyLink", "CollisionProxy", "Collision", None)
        _set_prop(obj, "App::PropertyLink", "DrapeTarget", "Collision", None)
    else:
        for name, prop in POSE_PROPERTY_MAP.items():
            _set_prop(obj, "App::PropertyAngle", prop, "Pose", 12.0 if "arm" in name else 0.0)
        for name, default in (("AvatarMeshProvider", ""), ("AvatarMeshSource", ""), ("AvatarMeshLicense", "")):
            _set_prop(obj, "App::PropertyString", name, "Avatar", default)
        for name in ("MeshVertexCount", "MeshTriangleCount"):
            _set_prop(obj, "App::PropertyInteger", name, "Avatar", 0)
    _rebuild(obj)
    collision = _ensure_collision(obj)
    target = _ensure_drape_target(obj)
    obj.CollisionProxy = collision
    obj.DrapeTarget = target
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
    obj.CollisionProxy = _ensure_collision(obj)
    obj.DrapeTarget = _ensure_drape_target(obj)
    return obj


def edit_avatar():
    import FreeCAD as App
    doc = App.ActiveDocument
    if doc is None:
        doc = App.newDocument("ClothSewing")
    obj = _avatar(doc) or create_avatar()
    from freecad_cloth.avatar.AvatarGui import show_avatar_task
    return show_avatar_task(obj)


def set_avatar_measurements(**changes):
    import FreeCAD as App
    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before changing avatar measurements")
    obj = _avatar(doc) or create_avatar()
    allowed = set(DEFAULT_MEASUREMENTS)
    for name, value in changes.items():
        key = str(name)
        if key not in allowed:
            raise ValueError("unknown avatar measurement: %s" % name)
        setattr(obj, PROPERTY_MAP[key], float(value))
    return rebuild_avatar()


def set_avatar_pose(pose):
    import FreeCAD as App
    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before changing avatar pose")
    obj = _avatar(doc) or create_avatar()
    Pose(str(pose), float(getattr(obj, "LeftArmAngle", 12)), float(getattr(obj, "RightArmAngle", 12)), float(getattr(obj, "LeftElbowAngle", 0)), float(getattr(obj, "RightElbowAngle", 0))).validate()
    obj.PosePreset = str(pose)
    return rebuild_avatar()


def set_avatar_skin_offset(offset):
    import FreeCAD as App
    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before changing avatar offset")
    obj = _avatar(doc) or create_avatar()
    obj.SkinOffset = float(offset)
    return rebuild_avatar()


def avatar_measurement(name):
    import FreeCAD as App
    doc = App.ActiveDocument
    if doc is None or _avatar(doc) is None:
        raise ValueError("create a Cloth Avatar first")
    return _parameters(_avatar(doc)).measurement(str(name))


def avatar_arrangement_points():
    """Return persisted local fitting points for the active humanoid mesh."""
    import FreeCAD as App
    doc = App.ActiveDocument
    if doc is None or _avatar(doc) is None:
        raise ValueError("create a Cloth Avatar first")
    return arrangement_points_from_landmarks(_avatar(doc).Landmarks)


COMMANDS = [
    "ClothFitting_CreateAvatar", "ClothFitting_EditAvatar", "ClothFitting_RebuildAvatar",
    "ClothFitting_SetAvatarMeasurements", "ClothFitting_SetAvatarPose", "ClothFitting_SetAvatarSkinOffset"
]
_HANDLERS = {
    "ClothFitting_CreateAvatar": create_avatar,
    "ClothFitting_EditAvatar": edit_avatar,
    "ClothFitting_RebuildAvatar": rebuild_avatar,
    "ClothFitting_SetAvatarMeasurements": lambda: set_avatar_measurements(height=1750, chest=980, waist=820, hip=1020),
    "ClothFitting_SetAvatarPose": lambda: set_avatar_pose("sewing"),
    "ClothFitting_SetAvatarSkinOffset": lambda: set_avatar_skin_offset(5.0),
}
try:
    import FreeCADGui as Gui
    from freecad_cloth.common.CommandAdapter import register_commands
    register_commands(Gui, _HANDLERS)
except (ImportError, AttributeError):
    pass
