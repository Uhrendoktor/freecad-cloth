"""FreeCAD-facing humanoid mesh avatar commands."""

from freecad_cloth.avatar.AvatarArrangement import arrangement_points_from_landmarks
from freecad_cloth.avatar.AvatarModel import (
    DEFAULT_MEASUREMENTS,
    AvatarParameters,
    Pose,
    generate_mesh,
)
from freecad_cloth.avatar.AvatarProvider import FreeCADGeometryAvatarProvider
from freecad_cloth.avatar.SkeletonPose import (
    JointRotation,
    joint_rotations_from_json,
    joint_rotations_to_json,
)

PROPERTY_MAP = {
    "height": "Height",
    "neck": "Neck",
    "shoulder": "Shoulder",
    "chest": "Chest",
    "underbust": "Underbust",
    "waist": "Waist",
    "high_hip": "High_Hip",
    "hip": "Hip",
    "upper_arm": "Upper_Arm",
    "elbow": "Elbow",
    "wrist": "Wrist",
    "thigh": "Thigh",
    "knee": "Knee",
    "calf": "Calf",
    "ankle": "Ankle",
    "inseam": "Inseam",
    "torso": "Torso",
    "front_waist": "Front_Waist",
    "back_waist": "Back_Waist",
}
POSE_PROPERTY_MAP = {
    "left_arm_angle": "LeftArmAngle",
    "right_arm_angle": "RightArmAngle",
    "left_elbow_angle": "LeftElbowAngle",
    "right_elbow_angle": "RightElbowAngle",
}
PROVIDER_IDS = ("makehuman-hm08", "freecad-geometry")
_MISSING = object()


def _avatar(doc):
    return next((o for o in doc.Objects if getattr(o, "AvatarType", "") == "ClothAvatar"), None)


def _set_prop(obj, kind, name, group, value):
    if not hasattr(obj, name):
        obj.addProperty(kind, name, group)
    setattr(obj, name, value)


def _parameters(obj):
    values = {name: float(getattr(obj, PROPERTY_MAP[name])) for name in DEFAULT_MEASUREMENTS}
    pose = Pose(
        str(obj.PosePreset),
        *(
            float(getattr(obj, POSE_PROPERTY_MAP[name], 12.0 if "arm" in name else 0.0))
            for name in (
                "left_arm_angle",
                "right_arm_angle",
                "left_elbow_angle",
                "right_elbow_angle",
            )
        ),
        tuple(joint_rotations_from_json(getattr(obj, "JointPoseJSON", ""))),
    )
    return AvatarParameters(values, float(obj.SkinOffset), pose)


def _mesh_data(vertices, triangles):
    """Build the native FreeCAD mesh directly from the selected provider topology."""
    import FreeCAD as App
    import Mesh

    native = Mesh.Mesh()
    vectors = [App.Vector(*point) for point in vertices]
    native.addFacets([(vectors[a], vectors[b], vectors[c]) for a, b, c in triangles])
    return native


def _style_mannequin(obj):
    """Give the body a neutral CAD-mannequin presentation, not a garment look."""
    try:
        view = obj.ViewObject
        view.DisplayMode = "Flat Lines"
        view.ShapeColor = (0.72, 0.72, 0.72)
        view.LineColor = (0.20, 0.20, 0.20)
        view.LineWidth = 1.0
    except (AttributeError, TypeError, ValueError):
        pass


def _provider_geometry(obj, params, provider_id=None, provider_source=_MISSING):
    provider_id = (
        str(getattr(obj, "AvatarProviderId", "makehuman-hm08"))
        if provider_id is None
        else str(provider_id)
    )
    if provider_id == "makehuman-hm08":
        vertices, triangles, landmarks = generate_mesh(params)
        source = "MakeHuman HM08 base mesh @ {}".format(
            __import__(
                "freecad_cloth.avatar.HumanoidMesh", fromlist=["MAKEHUMAN_COMMIT"]
            ).MAKEHUMAN_COMMIT
        )
        return vertices, triangles, landmarks, provider_id, source, "CC0"
    if provider_id == "freecad-geometry":
        source_obj = (
            getattr(obj, "ProviderSource", None)
            if provider_source is _MISSING
            else provider_source
        )
        if source_obj is None or source_obj is obj:
            raise ValueError("select a FreeCAD body as the avatar provider source")
        provider = FreeCADGeometryAvatarProvider(source_obj, deflection=1.0, thickness=0.0)
        vertices, triangles = provider.surface()
        source_name = getattr(source_obj, "Label", getattr(source_obj, "Name", "FreeCAD body"))
        return (
            vertices,
            triangles,
            (),
            provider_id,
            f"FreeCAD geometry: {source_name}",
            "Inherited from source object",
        )
    raise ValueError(f"unsupported avatar provider: {provider_id}")


def _rebuild(obj, params=None, provider_id=None, provider_source=_MISSING):
    """Build derived geometry before mutating persistent avatar state."""
    params = _parameters(obj) if params is None else params
    params.validate()
    if provider_id is None:
        provider_id = str(getattr(obj, "AvatarProviderId", "makehuman-hm08"))
    if provider_source is _MISSING:
        provider_source = getattr(obj, "ProviderSource", None)

    # All potentially fallible geometry/provider work happens before any
    # persistent avatar properties or derived mesh are changed.
    vertices, triangles, landmarks, provider_id, source, license_name = _provider_geometry(
        obj, params, provider_id, provider_source
    )
    native_mesh = _mesh_data(vertices, triangles)
    parameters_json = params.to_json()
    joint_json = joint_rotations_to_json(params.pose.joint_rotations)
    landmark_records = [
        f"{landmark.name}|{landmark.position[0]},{landmark.position[1]},{landmark.position[2]}"
        for landmark in landmarks
    ]
    arrangement_records = arrangement_points_from_landmarks(landmark_records)

    obj.Mesh = native_mesh
    for name, property_name in PROPERTY_MAP.items():
        setattr(obj, property_name, params.measurements[name])
    obj.PosePreset = params.pose.preset
    obj.SkinOffset = params.skin_offset
    for name, value in (
        ("left_arm_angle", params.pose.left_arm_angle),
        ("right_arm_angle", params.pose.right_arm_angle),
        ("left_elbow_angle", params.pose.left_elbow_angle),
        ("right_elbow_angle", params.pose.right_elbow_angle),
    ):
        setattr(obj, POSE_PROPERTY_MAP[name], value)
    _set_prop(obj, "App::PropertyString", "JointPoseJSON", "Pose", joint_json)
    obj.JointPoseJSON = joint_json
    obj.ParametersJSON = parameters_json
    obj.AvatarStatus = "Valid"
    obj.AvatarProviderId = provider_id
    obj.ProviderSource = provider_source if provider_id == "freecad-geometry" else None
    obj.AvatarMeshProvider = provider_id
    obj.AvatarMeshSource = source
    obj.AvatarMeshLicense = license_name
    obj.GarmentState = "Bare mannequin / provider geometry only"
    obj.MeshVertexCount = len(vertices)
    obj.MeshTriangleCount = len(triangles)
    obj.Landmarks = landmark_records
    if not hasattr(obj, "AvatarRevision"):
        _set_prop(obj, "App::PropertyInteger", "AvatarRevision", "Avatar", 0)
    obj.AvatarRevision = int(getattr(obj, "AvatarRevision", 0)) + 1
    _set_prop(obj, "App::PropertyStringList", "ArrangementPoints", "Fitting", [])
    obj.ArrangementPoints = arrangement_records
    _style_mannequin(obj)
    obj.Document.recompute()
    target = getattr(obj, "DrapeTarget", None) or obj.Document.getObject("DrapeTarget")
    if target is not None:
        from freecad_cloth.simulation.DrapeTarget import target_status

        status = target_status(target)
        target.TargetStatus = status["state"]
        target.InvalidationReason = status["reason"]
    return obj


def _ensure_collision(obj):
    """Maintain the legacy collision proxy as a derived display adapter only."""
    from freecad_cloth.simulation.SimulationObjects import create_avatar_collision

    avatar = obj.Document.getObject("AvatarCollision")
    if avatar is None:
        avatar = create_avatar_collision(obj.Document, obj, thickness=2.0, deflection=1.0)
    else:
        avatar.SourceObject = obj
        avatar.CollisionThickness = 2.0
        avatar.CollisionDeflection = 1.0
        from freecad_cloth.avatar.AvatarCollision import surface_from_freecad

        surface = surface_from_freecad(obj, 1.0, 2.0)
        avatar.CollisionType = "MeshSurface"
        avatar.CollisionVertexCount = len(surface.vertices)
        avatar.CollisionTriangleCount = len(surface.triangles)
    return avatar


def _ensure_drape_target(obj):
    """Attach the humanoid mesh to the target-neutral collision API."""
    from freecad_cloth.simulation.DrapeTarget import assign_drape_target, create_drape_target

    target = obj.Document.getObject("DrapeTarget")
    if target is None:
        target = create_drape_target(
            obj.Document, target_type="Mannequin", deflection=1.0, thickness=2.0
        )
    assign_drape_target(target, obj, "Mannequin")
    return target


def create_avatar(attach_collision=True, doc=None, object_name="ClothAvatar"):
    import FreeCAD as App

    doc = doc or App.ActiveDocument or App.newDocument("ClothSewing")
    obj = _avatar(doc)
    if obj is None:
        obj = doc.addObject("Mesh::Feature", object_name)
        obj.Label = "Cloth Human Avatar"
        _set_prop(obj, "App::PropertyString", "AvatarType", "Avatar", "ClothAvatar")
        _set_prop(obj, "App::PropertyString", "SchemaVersion", "Avatar", "1")
        _set_prop(obj, "App::PropertyEnumeration", "AvatarProviderId", "Avatar", list(PROVIDER_IDS))
        obj.AvatarProviderId = "makehuman-hm08"
        _set_prop(obj, "App::PropertyLink", "ProviderSource", "Avatar", None)
        for name, value in DEFAULT_MEASUREMENTS.items():
            _set_prop(obj, "App::PropertyLength", PROPERTY_MAP[name], "Measurements", value)
        _set_prop(obj, "App::PropertyLength", "SkinOffset", "Collision", 3.0)
        _set_prop(
            obj, "App::PropertyEnumeration", "PosePreset", "Pose", ["standing", "sewing", "sitting"]
        )
        obj.PosePreset = "standing"
        for name, prop in POSE_PROPERTY_MAP.items():
            _set_prop(obj, "App::PropertyAngle", prop, "Pose", 12.0 if "arm" in name else 0.0)
        _set_prop(
            obj, "App::PropertyString", "JointPoseJSON", "Pose", getattr(obj, "JointPoseJSON", "{}")
        )
        _set_prop(obj, "App::PropertyString", "AvatarStatus", "Avatar", "Unbuilt")
        _set_prop(obj, "App::PropertyString", "ParametersJSON", "Avatar", "")
        _set_prop(obj, "App::PropertyStringList", "Landmarks", "Measurements", [])
        _set_prop(obj, "App::PropertyStringList", "ArrangementPoints", "Fitting", [])
        _set_prop(obj, "App::PropertyString", "AvatarMeshProvider", "Avatar", "")
        _set_prop(obj, "App::PropertyString", "AvatarMeshSource", "Avatar", "")
        _set_prop(obj, "App::PropertyString", "AvatarMeshLicense", "Avatar", "")
        _set_prop(
            obj,
            "App::PropertyString",
            "GarmentState",
            "Avatar",
            "Bare mannequin / provider geometry only",
        )
        _set_prop(obj, "App::PropertyInteger", "MeshVertexCount", "Avatar", 0)
        _set_prop(obj, "App::PropertyInteger", "MeshTriangleCount", "Avatar", 0)
        _set_prop(obj, "App::PropertyLink", "CollisionProxy", "Collision", None)
        _set_prop(obj, "App::PropertyLink", "DrapeTarget", "Collision", None)
    else:
        _set_prop(obj, "App::PropertyEnumeration", "AvatarProviderId", "Avatar", list(PROVIDER_IDS))
        if not str(getattr(obj, "AvatarProviderId", "")):
            obj.AvatarProviderId = "makehuman-hm08"
        _set_prop(obj, "App::PropertyLink", "ProviderSource", "Avatar", None)
        for name, prop in POSE_PROPERTY_MAP.items():
            _set_prop(obj, "App::PropertyAngle", prop, "Pose", 12.0 if "arm" in name else 0.0)
        for name, default in (
            ("AvatarMeshProvider", ""),
            ("AvatarMeshSource", ""),
            ("AvatarMeshLicense", ""),
            ("GarmentState", "Bare mannequin / provider geometry only"),
        ):
            _set_prop(obj, "App::PropertyString", name, "Avatar", default)
        _set_prop(obj, "App::PropertyInteger", "MeshVertexCount", "Avatar", 0)
        _set_prop(obj, "App::PropertyInteger", "MeshTriangleCount", "Avatar", 0)
        _set_prop(
            obj,
            "App::PropertyInteger",
            "AvatarRevision",
            "Avatar",
            int(getattr(obj, "AvatarRevision", 0)),
        )
    _rebuild(obj)
    if attach_collision:
        _ensure_collision(obj)
        _ensure_drape_target(obj)
    from freecad_cloth.common.GarmentDocument import link_garment_object

    link_garment_object(obj, "Avatar", doc)
    doc.recompute()
    return obj


def apply_avatar_parameters(obj, params, provider_id=None, provider_source=_MISSING):
    """Apply validated avatar state only after successful geometry construction."""
    obj = _rebuild(
        obj,
        params=params,
        provider_id=provider_id,
        provider_source=provider_source,
    )
    _ensure_collision(obj)
    target = obj.Document.getObject("DrapeTarget")
    if target is None:
        _ensure_drape_target(obj)
    return obj


def rebuild_avatar():
    import FreeCAD as App

    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before rebuilding the avatar")
    obj = _avatar(doc)
    if obj is None:
        raise ValueError("create a Cloth Avatar first")
    return apply_avatar_parameters(obj, _parameters(obj))



def edit_avatar():
    import FreeCAD as App

    doc = App.ActiveDocument
    if doc is None:
        doc = App.newDocument("ClothSewing")
    obj = _avatar(doc) or create_avatar()
    from freecad_cloth.avatar.AvatarGui import show_avatar_task

    return show_avatar_task(obj)


def pose_avatar():
    """Open the focused 3D Pose Mode editor for the active mannequin."""
    import FreeCAD as App

    doc = App.ActiveDocument
    if doc is None:
        doc = App.newDocument("ClothSewing")
    obj = _avatar(doc) or create_avatar()
    from freecad_cloth.avatar.AvatarPoseGui import show_avatar_pose_task

    return show_avatar_pose_task(obj)


def set_avatar_measurements(**changes):
    import FreeCAD as App

    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before changing avatar measurements")
    obj = _avatar(doc) or create_avatar()
    current = _parameters(obj)
    for name in changes:
        if str(name) not in DEFAULT_MEASUREMENTS:
            raise ValueError(f"unknown avatar measurement: {name}")
    params = current.with_measurements(**changes)
    return apply_avatar_parameters(obj, params)


def set_avatar_pose(pose):
    import FreeCAD as App

    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before changing avatar pose")
    obj = _avatar(doc) or create_avatar()
    current = _parameters(obj)
    candidate = AvatarParameters(
        current.measurements,
        current.skin_offset,
        Pose(
            str(pose),
            current.pose.left_arm_angle,
            current.pose.right_arm_angle,
            current.pose.left_elbow_angle,
            current.pose.right_elbow_angle,
            current.pose.joint_rotations,
        ),
    )
    return apply_avatar_parameters(obj, candidate)


def set_avatar_joint(bone, x=0.0, y=0.0, z=0.0, mirror=False):
    """Persist one manual FK joint rotation and rebuild the mannequin."""
    import FreeCAD as App

    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before changing a mannequin joint")
    obj = _avatar(doc) or create_avatar()
    current = _parameters(obj)
    values = {rotation.bone: rotation for rotation in current.pose.joint_rotations}
    rotation = JointRotation(str(bone), float(x), float(y), float(z)).validate()
    values[rotation.bone] = rotation
    if mirror:
        values[rotation.mirrored().bone] = rotation.mirrored()
    candidate = AvatarParameters(
        current.measurements,
        current.skin_offset,
        Pose(
            current.pose.preset,
            current.pose.left_arm_angle,
            current.pose.right_arm_angle,
            current.pose.left_elbow_angle,
            current.pose.right_elbow_angle,
            tuple(values.values()),
        ),
    )
    return apply_avatar_parameters(obj, candidate)


def set_avatar_provider(provider_id, source=None):
    """Swap providers without replacing the avatar object or garment links."""
    import FreeCAD as App

    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before changing the avatar provider")
    obj = _avatar(doc) or create_avatar()
    provider_id = str(provider_id)
    if provider_id not in PROVIDER_IDS:
        raise ValueError(f"unsupported avatar provider: {provider_id}")
    if provider_id == "freecad-geometry":
        source = source or getattr(obj, "ProviderSource", None)
        if source is None or source is obj:
            raise ValueError(
                "a FreeCAD source object is required for the freecad-geometry provider"
            )
    else:
        source = None
    return apply_avatar_parameters(
        obj,
        _parameters(obj),
        provider_id=provider_id,
        provider_source=source,
    )


def set_avatar_skin_offset(offset):
    import FreeCAD as App

    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before changing avatar offset")
    obj = _avatar(doc) or create_avatar()
    current = _parameters(obj)
    candidate = AvatarParameters(
        current.measurements,
        float(offset),
        current.pose,
    )
    return apply_avatar_parameters(obj, candidate)



def avatar_measurement(name):
    import FreeCAD as App

    doc = App.ActiveDocument
    if doc is None or _avatar(doc) is None:
        raise ValueError("create a Cloth Avatar first")
    return _parameters(_avatar(doc)).measurement(str(name))


def avatar_arrangement_points():
    """Return persisted local fitting points for the active avatar mesh."""
    import FreeCAD as App

    doc = App.ActiveDocument
    if doc is None or _avatar(doc) is None:
        raise ValueError("create a Cloth Avatar first")
    return arrangement_points_from_landmarks(_avatar(doc).Landmarks)


COMMANDS = [
    "ClothFitting_CreateAvatar",
    "ClothFitting_EditAvatar",
    "ClothFitting_PoseAvatar",
    "ClothFitting_RebuildAvatar",
    "ClothFitting_SetAvatarMeasurements",
    "ClothFitting_SetAvatarPose",
    "ClothFitting_SetAvatarProvider",
    "ClothFitting_SetAvatarJoint",
    "ClothFitting_SetAvatarSkinOffset",
]
_HANDLERS = {
    "ClothFitting_CreateAvatar": create_avatar,
    "ClothFitting_EditAvatar": edit_avatar,
    "ClothFitting_PoseAvatar": pose_avatar,
    "ClothFitting_RebuildAvatar": rebuild_avatar,
    "ClothFitting_SetAvatarMeasurements": lambda: set_avatar_measurements(
        height=1750, chest=980, waist=820, hip=1020
    ),
    "ClothFitting_SetAvatarPose": lambda: set_avatar_pose("sewing"),
    "ClothFitting_SetAvatarProvider": lambda: set_avatar_provider("makehuman-hm08"),
    "ClothFitting_SetAvatarJoint": lambda: set_avatar_joint("upperarm01.L", y=-45.0, mirror=True),
    "ClothFitting_SetAvatarSkinOffset": lambda: set_avatar_skin_offset(5.0),
}
try:
    import FreeCADGui as Gui

    from freecad_cloth.common.CommandAdapter import register_commands

    register_commands(Gui, _HANDLERS)
except (ImportError, AttributeError):
    pass
