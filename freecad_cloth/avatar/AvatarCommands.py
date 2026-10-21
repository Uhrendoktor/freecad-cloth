# Copyright (C) 2026 FreeCAD Cloth contributors
"""FreeCAD-facing humanoid mesh avatar commands."""

import json
from collections.abc import Callable
from contextlib import suppress
from itertools import starmap
from types import ModuleType

from freecad_cloth.avatar.AvatarArrangement import arrangement_points_from_landmarks
from freecad_cloth.avatar.AvatarModel import (
    DEFAULT_MEASUREMENTS,
    AvatarParameters,
    Landmark,
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
    "stomach": "Stomach",
    "sleeve_length": "Sleeve_Length",
    "crotch_length": "Crotch_Length",
    "front_rise": "Front_Rise",
    "back_rise": "Back_Rise",
    "shirt_length": "Shirt_Length",
    "back_neck_to_waist": "Back_Neck_To_Waist",
}
SHAPE_PROPERTY_MAP = {
    "gender": "GenderBlend",
    "breast_size": "BreastSize",
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


def _ensure_pose_preset_property(obj):
    """Upgrade the saved preset enumeration without losing the user's current choice."""
    current = str(getattr(obj, "PosePreset", "standing"))
    presets = ["standing", "sewing", "sitting", "t_pose"]
    _set_prop(obj, "App::PropertyEnumeration", "PosePreset", "Pose", presets)
    obj.PosePreset = current if current in presets else "standing"


def _parameters(obj):
    values = {name: float(getattr(obj, PROPERTY_MAP[name])) for name in DEFAULT_MEASUREMENTS}
    preset = str(getattr(obj, "PosePreset", "standing"))
    preset_defaults = Pose(preset)
    fallback = {
        "left_arm_angle": float(preset_defaults.left_arm_angle),
        "right_arm_angle": float(preset_defaults.right_arm_angle),
        "left_elbow_angle": float(preset_defaults.left_elbow_angle),
        "right_elbow_angle": float(preset_defaults.right_elbow_angle),
    }
    angles = {
        name: float(getattr(obj, POSE_PROPERTY_MAP[name], fallback[name])) for name in fallback
    }

    # Migrate the stored schema once at the document boundary. New pose code uses
    # explicit defaults, not 12° magic values during geometry generation.
    payload = str(getattr(obj, "ParametersJSON", "") or "")
    if payload:
        try:
            stored_data = json.loads(payload)
            stored_pose_data = stored_data.get("pose", {})
            if int(stored_data.get("schema_version", 1)) == 1:
                stored_pose = AvatarParameters.from_json(payload).pose
                if str(stored_pose_data.get("preset", "standing")) == preset:
                    for name in ("left_arm_angle", "right_arm_angle"):
                        serialized = float(stored_pose_data.get(name, 12.0))
                        if angles[name] == serialized:
                            angles[name] = float(getattr(stored_pose, name))
        except (TypeError, ValueError):
            pass

    pose = Pose(
        preset,
        angles["left_arm_angle"],
        angles["right_arm_angle"],
        angles["left_elbow_angle"],
        angles["right_elbow_angle"],
        tuple(joint_rotations_from_json(getattr(obj, "JointPoseJSON", ""))),
    )
    shape_payload = {}
    phenotype_overrides = {}
    local_change_overrides = {}
    mass_target_kg = None
    if payload:
        with suppress(TypeError, ValueError):
            stored_parameters = AvatarParameters.from_json(payload)
            shape_payload = json.loads(payload).get("shape", {})
            phenotype_overrides = dict(stored_parameters.phenotype_overrides)
            local_change_overrides = dict(stored_parameters.local_change_overrides)
            mass_target_kg = stored_parameters.mass_target_kg
    gender = float(getattr(obj, SHAPE_PROPERTY_MAP["gender"], shape_payload.get("gender", 0.5)))
    breast_size = float(
        getattr(obj, SHAPE_PROPERTY_MAP["breast_size"], shape_payload.get("breast_size", 0.0))
    )
    return AvatarParameters(
        values,
        float(obj.SkinOffset),
        pose,
        4,
        gender,
        breast_size,
        phenotype_overrides,
        local_change_overrides,
        mass_target_kg,
    )


def _mesh_data(
    vertices,
    triangles,
    *,
    app_module: ModuleType | None = None,
    mesh_module: ModuleType | None = None,
):
    """Build the native FreeCAD mesh directly from the selected provider topology."""
    if app_module is None:
        import FreeCAD as app_module
    if mesh_module is None:
        import Mesh as mesh_module

    native = mesh_module.Mesh()
    vectors = list(starmap(app_module.Vector, vertices))
    # Preserve the provider's shared vertex indices. Passing one vector triple
    # per face builds disconnected facet topology in FreeCAD Mesh, so the
    # downstream collision adapter cannot recognize the closed mannequin shell.
    native.addFacets((vectors, list(triangles)), False)
    return native


def _style_mannequin(obj: object) -> None:
    """Apply a neutral CAD-mannequin presentation to a body.

    Args:
        obj: FreeCAD document object whose view properties should be styled.
    """
    try:
        view = getattr(obj, "ViewObject")
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
        source = "Anny parametric body model / clad-body measurements"
        return vertices, triangles, landmarks, provider_id, source, "Apache-2.0 / CC0"
    if provider_id == "freecad-geometry":
        source_obj = (
            getattr(obj, "ProviderSource", None) if provider_source is _MISSING else provider_source
        )
        if source_obj is None or source_obj is obj:
            msg = "select a FreeCAD body as the avatar provider source"
            raise ValueError(msg)
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
    msg = f"unsupported avatar provider: {provider_id}"
    raise ValueError(msg)


def _rebuild(
    obj,
    params=None,
    provider_id=None,
    provider_source=_MISSING,
    *,
    provider_geometry_fn: Callable[
        ...,
        tuple[
            tuple[tuple[float, float, float], ...],
            tuple[tuple[int, int, int], ...],
            tuple[Landmark, ...],
            str,
            str,
            str,
        ],
    ]
    | None = None,
):
    """Build derived geometry before mutating persistent avatar state."""
    params = _parameters(obj) if params is None else params
    params.validate()
    if provider_id is None:
        provider_id = str(getattr(obj, "AvatarProviderId", "makehuman-hm08"))
    if provider_source is _MISSING:
        provider_source = getattr(obj, "ProviderSource", None)

    # All potentially fallible geometry/provider work happens before any
    # persistent avatar properties or derived mesh are changed.
    build_geometry = _provider_geometry if provider_geometry_fn is None else provider_geometry_fn
    vertices, triangles, landmarks, provider_id, source, license_name = build_geometry(
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
    for name, property_name in SHAPE_PROPERTY_MAP.items():
        _set_prop(
            obj, "App::PropertyFloat", property_name, "Body shape", 0.5 if name == "gender" else 0.0
        )
        setattr(obj, property_name, float(getattr(params, name)))
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
    from freecad_cloth.avatar.AvatarCollision import ensure_collision_proxy

    return ensure_collision_proxy(obj.Document, obj, thickness=2.0, deflection=1.0)


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


def create_avatar(
    attach_collision=True,
    doc=None,
    object_name="ClothAvatar",
    params: AvatarParameters | None = None,
):
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
        _set_prop(obj, "App::PropertyFloat", "GenderBlend", "Body shape", 0.5)
        _set_prop(obj, "App::PropertyFloat", "BreastSize", "Body shape", 0.0)
        _set_prop(obj, "App::PropertyLength", "SkinOffset", "Collision", 3.0)
        _set_prop(
            obj,
            "App::PropertyEnumeration",
            "PosePreset",
            "Pose",
            ["standing", "sewing", "sitting", "t_pose"],
        )
        obj.PosePreset = "standing"
        default_pose = Pose("standing")
        for name, prop in POSE_PROPERTY_MAP.items():
            _set_prop(
                obj,
                "App::PropertyAngle",
                prop,
                "Pose",
                float(getattr(default_pose, name)),
            )
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
        _ensure_pose_preset_property(obj)
        _set_prop(obj, "App::PropertyEnumeration", "AvatarProviderId", "Avatar", list(PROVIDER_IDS))
        if not str(getattr(obj, "AvatarProviderId", "")):
            obj.AvatarProviderId = "makehuman-hm08"
        _set_prop(obj, "App::PropertyLink", "ProviderSource", "Avatar", None)
        _set_prop(
            obj,
            "App::PropertyFloat",
            "GenderBlend",
            "Body shape",
            float(getattr(obj, "GenderBlend", 0.5)),
        )
        _set_prop(
            obj,
            "App::PropertyFloat",
            "BreastSize",
            "Body shape",
            float(getattr(obj, "BreastSize", 0.0)),
        )
        default_pose = Pose(str(getattr(obj, "PosePreset", "standing")))
        for name, prop in POSE_PROPERTY_MAP.items():
            if not hasattr(obj, prop):
                _set_prop(
                    obj,
                    "App::PropertyAngle",
                    prop,
                    "Pose",
                    float(getattr(default_pose, name)),
                )
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
    _rebuild(obj, params=params)
    if attach_collision:
        _ensure_collision(obj)
        _ensure_drape_target(obj)
    from freecad_cloth.common.GarmentDocument import link_garment_object

    link_garment_object(obj, "Avatar", doc)
    doc.recompute()
    return obj


def apply_avatar_parameters(
    obj,
    params,
    provider_id=None,
    provider_source=_MISSING,
    *,
    provider_geometry_fn: Callable[
        ...,
        tuple[
            tuple[tuple[float, float, float], ...],
            tuple[tuple[int, int, int], ...],
            tuple[Landmark, ...],
            str,
            str,
            str,
        ],
    ]
    | None = None,
):
    """Apply validated avatar state only after successful geometry construction."""
    obj = _rebuild(
        obj,
        params=params,
        provider_id=provider_id,
        provider_source=provider_source,
        provider_geometry_fn=provider_geometry_fn,
    )
    _ensure_collision(obj)
    target = obj.Document.getObject("DrapeTarget")
    if target is None:
        _ensure_drape_target(obj)

    # Avatar pose edits regenerate the mesh in-place. Refresh fitting anchors
    # after the final mesh exists so their saved triangle/barycentric reference
    # follows the deformed surface instead of being invalidated by AvatarRevision.
    try:
        from freecad_cloth.avatar.FittingCommands import _refresh_anchor_positions, _scene

        fitting_scene = _scene(obj.Document)
        if fitting_scene is not None and getattr(fitting_scene, "AvatarProxy", None) == obj:
            _refresh_anchor_positions(fitting_scene, update_visuals=True)
    except (AttributeError, ImportError, RuntimeError, TypeError, ValueError):
        # Avatar creation/rebuild must remain independent of the optional fitting scene.
        pass
    return obj


def rebuild_avatar():
    import FreeCAD as App

    doc = App.ActiveDocument
    if doc is None:
        msg = "open a document before rebuilding the avatar"
        raise ValueError(msg)
    obj = _avatar(doc)
    if obj is None:
        msg = "create a Cloth Avatar first"
        raise ValueError(msg)
    _ensure_pose_preset_property(obj)
    return apply_avatar_parameters(obj, _parameters(obj))


def edit_avatar():
    import FreeCAD as App

    doc = App.ActiveDocument
    if doc is None:
        doc = App.newDocument("ClothSewing")
    obj = _avatar(doc) or create_avatar()
    _ensure_pose_preset_property(obj)
    from freecad_cloth.avatar.AvatarGui import show_avatar_task

    return show_avatar_task(obj)


def pose_avatar():
    """Open the focused 3D Pose Mode editor for the active mannequin."""
    import FreeCAD as App

    doc = App.ActiveDocument
    if doc is None:
        doc = App.newDocument("ClothSewing")
    obj = _avatar(doc) or create_avatar()
    _ensure_pose_preset_property(obj)
    from freecad_cloth.avatar.AvatarPoseGui import show_avatar_pose_task

    return show_avatar_pose_task(obj)


def set_avatar_measurements(**changes):
    import FreeCAD as App

    doc = App.ActiveDocument
    if doc is None:
        msg = "open a document before changing avatar measurements"
        raise ValueError(msg)
    obj = _avatar(doc) or create_avatar()
    current = _parameters(obj)
    for name in changes:
        if str(name) not in DEFAULT_MEASUREMENTS:
            msg = f"unknown avatar measurement: {name}"
            raise ValueError(msg)
    params = current.with_measurements(**changes)
    return apply_avatar_parameters(obj, params)


def set_avatar_pose(pose):
    import FreeCAD as App

    doc = App.ActiveDocument
    if doc is None:
        msg = "open a document before changing avatar pose"
        raise ValueError(msg)
    obj = _avatar(doc) or create_avatar()
    _ensure_pose_preset_property(obj)
    current = _parameters(obj)
    # Choosing a named preset means starting from that pose's canonical baseline,
    # just as the Pose Mode buttons do; do not carry unrelated manual rotations over.
    candidate = AvatarParameters(
        current.measurements,
        current.skin_offset,
        Pose(str(pose)),
        4,
        current.gender,
        current.breast_size,
        current.phenotype_overrides,
        current.local_change_overrides,
        current.mass_target_kg,
    )
    return apply_avatar_parameters(obj, candidate)


def set_avatar_joint(bone, x=0.0, y=0.0, z=0.0, mirror=False):
    """Persist one manual FK joint rotation and rebuild the mannequin."""
    import FreeCAD as App

    doc = App.ActiveDocument
    if doc is None:
        msg = "open a document before changing a mannequin joint"
        raise ValueError(msg)
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
        4,
        current.gender,
        current.breast_size,
        current.phenotype_overrides,
        current.local_change_overrides,
        current.mass_target_kg,
    )
    return apply_avatar_parameters(obj, candidate)


def set_avatar_provider(provider_id, source=None):
    """Swap providers without replacing the avatar object or garment links."""
    import FreeCAD as App

    doc = App.ActiveDocument
    if doc is None:
        msg = "open a document before changing the avatar provider"
        raise ValueError(msg)
    obj = _avatar(doc) or create_avatar()
    provider_id = str(provider_id)
    if provider_id not in PROVIDER_IDS:
        msg = f"unsupported avatar provider: {provider_id}"
        raise ValueError(msg)
    if provider_id == "freecad-geometry":
        source = source or getattr(obj, "ProviderSource", None)
        if source is None or source is obj:
            msg = "a FreeCAD source object is required for the freecad-geometry provider"
            raise ValueError(msg)
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
        msg = "open a document before changing avatar offset"
        raise ValueError(msg)
    obj = _avatar(doc) or create_avatar()
    current = _parameters(obj)
    candidate = AvatarParameters(
        current.measurements,
        float(offset),
        current.pose,
        4,
        current.gender,
        current.breast_size,
        current.phenotype_overrides,
        current.local_change_overrides,
        current.mass_target_kg,
    )
    return apply_avatar_parameters(obj, candidate)


def avatar_measurement(name):
    import FreeCAD as App

    doc = App.ActiveDocument
    if doc is None or _avatar(doc) is None:
        msg = "create a Cloth Avatar first"
        raise ValueError(msg)
    return _parameters(_avatar(doc)).measurement(str(name))


def avatar_arrangement_points():
    """Return persisted local fitting points for the active avatar mesh."""
    import FreeCAD as App

    doc = App.ActiveDocument
    if doc is None or _avatar(doc) is None:
        msg = "create a Cloth Avatar first"
        raise ValueError(msg)
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
