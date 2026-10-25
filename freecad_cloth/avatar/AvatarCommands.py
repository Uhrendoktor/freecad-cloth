# Copyright (C) 2026 FreeCAD Cloth contributors
"""FreeCAD-facing humanoid mesh avatar commands."""

from collections.abc import Callable, Sequence
from itertools import starmap
from types import ModuleType
from typing import Protocol, cast

from freecad_cloth.avatar.CommandIds import AVATAR_COMMANDS
from freecad_cloth.avatar.AvatarProperties import (
    POSE_PROPERTY_MAP,
    PROPERTY_MAP,
    PROVIDER_IDS,
    SHAPE_PROPERTY_MAP,
)
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

_MISSING = object()
ProviderGeometry = Callable[
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


class _AvatarViewObject(Protocol):
    """Writable FreeCAD view-provider properties used by avatar styling.

    Attributes:
        DisplayMode: View mode used to render the mannequin mesh.
        ShapeColor: RGB fill color assigned to the mannequin mesh.
        LineColor: RGB edge color assigned to the mannequin mesh.
        LineWidth: Width of the visible mesh edges.
    """

    DisplayMode: str
    ShapeColor: tuple[float, float, float]
    LineColor: tuple[float, float, float]
    LineWidth: float


class _AvatarFeatureView(Protocol):
    """FreeCAD feature interface needed to obtain its view provider.

    Attributes:
        ViewObject: Provider exposing the mannequin display properties.
    """

    ViewObject: _AvatarViewObject


class _FreeCADDocument(Protocol):
    """Document members used by the persistent avatar command boundary."""

    Objects: Sequence[object]

    def addObject(self, object_type: str, object_name: str) -> object:
        """Create a native document object using FreeCAD's API.

        Args:
            object_type: Native FreeCAD object type identifier.
            object_name: Internal document name for the new object.

        Returns:
            The newly created document object.
        """
        ...

    def getObject(self, object_name: str) -> object | None:
        """Return a document object by its internal name, if present.

        Args:
            object_name: Internal document name to look up.

        Returns:
            The matching document object, or None when no object has that name.
        """
        ...

    recompute: Callable[[], None]


class _AvatarFeature(_AvatarFeatureView, Protocol):
    """Dynamic FreeCAD avatar properties used by its command lifecycle."""

    Label: str
    Document: _FreeCADDocument
    Mesh: object
    PosePreset: str
    SkinOffset: float
    JointPoseJSON: str
    ParametersJSON: str
    AvatarStatus: str
    AvatarProviderId: str
    ProviderSource: object | None
    AvatarMeshProvider: str
    AvatarMeshSource: str
    AvatarMeshLicense: str
    GarmentState: str
    MeshVertexCount: int
    MeshTriangleCount: int
    Landmarks: list[str]
    AvatarRevision: int
    ArrangementPoints: list[str]

    def addProperty(self, kind: str, name: str, group: str) -> object:
        """Register a property on the FreeCAD feature.

        Args:
            kind: FreeCAD property type identifier.
            name: Attribute name to register on the feature.
            group: Property-editor group that contains the attribute.

        Returns:
            The native property-registration result.
        """
        ...


class _FreeCADApplication(Protocol):
    """Active-document functions dynamically exported by the FreeCAD module."""

    ActiveDocument: _FreeCADDocument | None

    def newDocument(self, name: str) -> _FreeCADDocument:
        """Create a FreeCAD document with the requested internal name.

        Args:
            name: Internal name for the new document.

        Returns:
            The created document, which becomes the active document.
        """
        ...


class _DrapeTarget(Protocol):
    """Writable status fields on the simulation's persistent drape target."""

    TargetStatus: str
    InvalidationReason: str


def _avatar(doc: _FreeCADDocument) -> _AvatarFeature | None:
    """Find the existing avatar feature in a FreeCAD document.

    Args:
        doc: Document whose objects should be searched.

    Returns:
        The first persisted ClothAvatar object, or None when absent.
    """
    for candidate in doc.Objects:
        if getattr(candidate, "AvatarType", "") == "ClothAvatar":
            return cast("_AvatarFeature", candidate)
    return None


def _set_prop(obj: _AvatarFeature, kind: str, name: str, group: str, value: object) -> None:
    """Create a FreeCAD property if needed, then assign its initial value.

    Args:
        obj: Document object receiving the property.
        kind: FreeCAD property type identifier.
        name: Property name to create or update.
        group: Property group displayed in the property editor.
        value: Initial value assigned to the property.
    """
    if not hasattr(obj, name):
        obj.addProperty(kind, name, group)
    setattr(obj, name, value)


def _parameters(obj: _AvatarFeature) -> AvatarParameters:
    """Reconstruct validated avatar parameters from the current persisted schema.

    Args:
        obj: Avatar object containing the complete current property schema.

    Returns:
        Parameter model representing the saved avatar state.

    Raises:
        ValueError: If the saved parameter JSON violates the current schema.
        TypeError: If a persistent property has an invalid type.
    """
    values = {name: float(getattr(obj, PROPERTY_MAP[name])) for name in DEFAULT_MEASUREMENTS}
    preset = str(obj.PosePreset)
    angles = {
        name: float(getattr(obj, property_name))
        for name, property_name in POSE_PROPERTY_MAP.items()
    }
    pose = Pose(
        preset,
        angles["left_arm_angle"],
        angles["right_arm_angle"],
        angles["left_elbow_angle"],
        angles["right_elbow_angle"],
        tuple(joint_rotations_from_json(obj.JointPoseJSON)),
    )

    payload = str(obj.ParametersJSON or "")
    phenotype_overrides = {}
    local_change_overrides = {}
    mass_target_kg = None
    if payload:
        stored_parameters = AvatarParameters.from_json(payload)
        phenotype_overrides = dict(stored_parameters.phenotype_overrides)
        local_change_overrides = dict(stored_parameters.local_change_overrides)
        mass_target_kg = stored_parameters.mass_target_kg

    return AvatarParameters(
        values,
        float(obj.SkinOffset),
        pose,
        4,
        float(getattr(obj, SHAPE_PROPERTY_MAP["gender"])),
        float(getattr(obj, SHAPE_PROPERTY_MAP["breast_size"])),
        phenotype_overrides,
        local_change_overrides,
        mass_target_kg,
    )


def _mesh_data(
    vertices: tuple[tuple[float, float, float], ...],
    triangles: tuple[tuple[int, int, int], ...],
    *,
    app_module: ModuleType | None = None,
    mesh_module: ModuleType | None = None,
) -> object:
    """Build the native FreeCAD mesh directly from the selected provider topology.

    Args:
        vertices: Shared 3D coordinates supplied by the selected avatar provider.
        triangles: Indexed triangular faces forming the provider topology.
        app_module: Optional FreeCAD module supplied by tests or runtime bootstrap.
        mesh_module: Optional Mesh module supplied by tests or runtime bootstrap.

    Returns:
        A native Mesh object with the provider's shared vertex topology preserved.
    """
    if app_module is None:
        import FreeCAD as app_module
    if mesh_module is None:
        import Mesh as mesh_module

    native = mesh_module.Mesh()
    vectors = list(starmap(app_module.Vector, vertices))
    # Preserve the provider's shared vertex indices. Passing one vector triple
    # per face builds disconnected facet topology in FreeCAD Mesh, so the
    # downstream collision adapter cannot recognize the closed mannequin shell.
    check_manifolds = False
    native.addFacets((vectors, list(triangles)), check_manifolds)
    return native


def _style_mannequin(obj: _AvatarFeature) -> None:
    """Apply a neutral CAD-mannequin presentation to a body.

    Args:
        obj: FreeCAD document object whose view properties should be styled.
    """
    try:
        view = cast("_AvatarFeatureView", obj).ViewObject
        view.DisplayMode = "Flat Lines"
        view.ShapeColor = (0.72, 0.72, 0.72)
        view.LineColor = (0.20, 0.20, 0.20)
        view.LineWidth = 1.0
    except (AttributeError, TypeError, ValueError):
        pass


def _provider_geometry(
    obj: _AvatarFeature,
    params: AvatarParameters,
    provider_id: str | None = None,
    provider_source: object = _MISSING,
) -> tuple[
    tuple[tuple[float, float, float], ...],
    tuple[tuple[int, int, int], ...],
    tuple[Landmark, ...],
    str,
    str,
    str,
]:
    """Build avatar geometry and provenance through the selected provider.

    Args:
        obj: Existing avatar object that stores the provider configuration.
        params: Validated measurements and pose used to generate the geometry.
        provider_id: Optional provider identifier overriding the saved selection.
        provider_source: Optional source object for the FreeCAD geometry provider.

    Returns:
        Vertices, faces, landmarks, provider identifier, source label, and license.

    Raises:
        ValueError: If the provider identifier or required source object is invalid.
    """
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


def _refresh_drape_target_status(obj: _AvatarFeature) -> None:
    """Refresh derived status properties for the active drape target.

    Args:
        obj: Avatar feature whose document may contain a drape target.

    """
    target = getattr(obj, "DrapeTarget", None)
    if target is None:
        target = obj.Document.getObject("DrapeTarget")
    if target is None:
        return
    typed_target = cast("_DrapeTarget", target)
    from freecad_cloth.simulation import DrapeTarget as drape_target

    status = drape_target.target_status(typed_target)
    typed_target.TargetStatus = status["state"]
    typed_target.InvalidationReason = status["reason"]


def _rebuild(
    obj: _AvatarFeature,
    params: AvatarParameters | None = None,
    provider_id: str | None = None,
    provider_source: object = _MISSING,
    *,
    provider_geometry_fn: ProviderGeometry | None = None,
) -> _AvatarFeature:
    """Build derived geometry before mutating persistent avatar state.

    Args:
        obj: Persisted FreeCAD avatar feature to rebuild.
        params: Optional validated parameter state; saved properties are used by default.
        provider_id: Optional provider identifier overriding the saved selection.
        provider_source: Optional body used by the FreeCAD geometry provider.
        provider_geometry_fn: Optional provider callback used by focused tests.

    Returns:
        The same avatar feature after its mesh and derived properties are refreshed.
    """
    params = _parameters(obj) if params is None else params
    params.validate()
    if provider_id is None:
        provider_id = str(obj.AvatarProviderId)
    if provider_source is _MISSING:
        provider_source = obj.ProviderSource

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
    obj.AvatarRevision = int(obj.AvatarRevision) + 1
    obj.ArrangementPoints = arrangement_records
    _style_mannequin(obj)
    obj.Document.recompute()
    _refresh_drape_target_status(obj)
    return obj


def _ensure_drape_target(obj: _AvatarFeature) -> object:
    """Attach the humanoid mesh to the target-neutral collision API.

    Args:
        obj: Avatar feature assigned as the mannequin collision target.

    Returns:
        The created or updated drape-target object.
    """
    from freecad_cloth.simulation import DrapeTarget as drape_target

    target = obj.Document.getObject("DrapeTarget")
    if target is None:
        target = drape_target.create_drape_target(
            obj.Document, target_type="Mannequin", deflection=1.0, thickness=2.0
        )
    drape_target.assign_drape_target(target, obj, "Mannequin")
    return target


def _initialize_avatar_properties(obj: _AvatarFeature) -> None:
    """Add the complete initial property schema to a new avatar feature.

    Args:
        obj: New FreeCAD mesh feature that will persist mannequin parameters.

    """
    _set_prop(obj, "App::PropertyString", "AvatarType", "Avatar", "ClothAvatar")
    _set_prop(obj, "App::PropertyEnumeration", "AvatarProviderId", "Avatar", list(PROVIDER_IDS))
    obj.AvatarProviderId = "makehuman-hm08"
    _set_prop(obj, "App::PropertyLink", "ProviderSource", "Avatar", None)
    for name, value in DEFAULT_MEASUREMENTS.items():
        _set_prop(obj, "App::PropertyLength", PROPERTY_MAP[name], "Measurements", value)
    _set_prop(obj, "App::PropertyFloat", SHAPE_PROPERTY_MAP["gender"], "Body shape", 0.5)
    _set_prop(obj, "App::PropertyFloat", SHAPE_PROPERTY_MAP["breast_size"], "Body shape", 0.0)
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
        obj, "App::PropertyString", "JointPoseJSON", "Pose", joint_rotations_to_json(())
    )
    _set_prop(obj, "App::PropertyString", "AvatarStatus", "Avatar", "Unbuilt")
    _set_prop(obj, "App::PropertyString", "ParametersJSON", "Avatar", "")
    _set_prop(obj, "App::PropertyStringList", "Landmarks", "Measurements", [])
    _set_prop(obj, "App::PropertyStringList", "ArrangementPoints", "Fitting", [])
    _set_prop(obj, "App::PropertyInteger", "AvatarRevision", "Avatar", 0)
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
    _set_prop(obj, "App::PropertyLink", "DrapeTarget", "Collision", None)


def create_avatar(
    doc: object | None = None,
    object_name: str = "ClothAvatar",
    params: AvatarParameters | None = None,
    *,
    attach_collision: bool = True,
) -> _AvatarFeature:
    """Create or rebuild the active mannequin avatar feature.

    Args:
        attach_collision: Whether to attach collision proxy and target objects.
        doc: Optional FreeCAD document; the active document is used by default.
        object_name: Name assigned when a new avatar feature is created.
        params: Optional validated parameters overriding the saved defaults.

    Returns:
        The created or updated avatar feature.
    """
    import FreeCAD as App

    app = cast("_FreeCADApplication", App)

    doc = cast(
        "_FreeCADDocument",
        doc or app.ActiveDocument or app.newDocument("ClothSewing"),
    )
    obj = _avatar(doc)
    if obj is None:
        obj = cast("_AvatarFeature", doc.addObject("Mesh::Feature", object_name))
        obj.Label = "Cloth Human Avatar"
        _initialize_avatar_properties(obj)
    _rebuild(obj, params=params)
    if attach_collision:
        _ensure_drape_target(obj)
    from freecad_cloth.common import GarmentDocument as garment_document

    garment_document.link_garment_object(obj, "Avatar", doc)
    doc.recompute()
    return obj


def apply_avatar_parameters(
    obj: object,
    params: AvatarParameters,
    provider_id: str | None = None,
    provider_source: object = _MISSING,
    *,
    provider_geometry_fn: ProviderGeometry | None = None,
) -> _AvatarFeature:
    """Apply validated avatar state only after successful geometry construction.

    Args:
        obj: Existing avatar feature to update in place.
        params: Validated measurements, shape values, and pose settings to apply.
        provider_id: Optional geometry provider identifier overriding saved state.
        provider_source: Optional source body for the FreeCAD geometry provider.
        provider_geometry_fn: Optional geometry callback for focused validation.

    Returns:
        The updated avatar feature after derived collision and fitting links refresh.
    """
    typed_obj = cast("_AvatarFeature", obj)
    obj = _rebuild(
        typed_obj,
        params=params,
        provider_id=provider_id,
        provider_source=provider_source,
        provider_geometry_fn=provider_geometry_fn,
    )
    target = obj.Document.getObject("DrapeTarget")
    if target is None:
        _ensure_drape_target(obj)

    # Avatar pose edits regenerate the mesh in-place. Refresh fitting anchors
    # after the final mesh exists so their saved triangle/barycentric reference
    # follows the deformed surface instead of being invalidated by AvatarRevision.
    try:
        from freecad_cloth.avatar import FittingCommands as fitting_commands
        fitting_scene = fitting_commands._scene(obj.Document)
        drape_target = obj.Document.getObject("DrapeTarget")
        if fitting_scene is not None and getattr(drape_target, "SourceObject", None) is obj:
            fitting_commands._refresh_anchor_positions(fitting_scene, update_visuals=True)
    except (AttributeError, ImportError, RuntimeError, TypeError, ValueError):
        # Avatar creation/rebuild must remain independent of the optional fitting scene.
        pass
    return obj


def rebuild_avatar() -> _AvatarFeature:
    """Rebuild the active avatar from the parameters saved in its document.

    Returns:
        The rebuilt avatar feature.

    Raises:
        ValueError: If no document is active or the document has no avatar feature.
    """
    import FreeCAD as App

    app = cast("_FreeCADApplication", App)

    doc = app.ActiveDocument
    if doc is None:
        msg = "open a document before rebuilding the avatar"
        raise ValueError(msg)
    obj = _avatar(doc)
    if obj is None:
        msg = "create a Cloth Avatar first"
        raise ValueError(msg)
    return apply_avatar_parameters(obj, _parameters(obj))


def edit_avatar() -> _AvatarFeature:
    """Open the avatar measurement and shape editor.

    Returns:
        The task-panel instance shown by FreeCAD.
    """
    import FreeCAD as App

    app = cast("_FreeCADApplication", App)

    doc = app.ActiveDocument
    if doc is None:
        doc = app.newDocument("ClothSewing")
    obj = _avatar(doc) or create_avatar()
    from freecad_cloth.avatar import AvatarGui as avatar_gui
    return avatar_gui.show_avatar_task(obj)


def pose_avatar() -> _AvatarFeature:
    """Open the focused 3D Pose Mode editor for the active mannequin.

    Returns:
        The pose task-panel instance shown by FreeCAD.
    """
    import FreeCAD as App

    app = cast("_FreeCADApplication", App)

    doc = app.ActiveDocument
    if doc is None:
        doc = app.newDocument("ClothSewing")
    obj = _avatar(doc) or create_avatar()
    from freecad_cloth.avatar import AvatarPoseGui as avatar_pose_gui
    return avatar_pose_gui.show_avatar_pose_task(obj)


def set_avatar_measurements(**changes: float) -> _AvatarFeature:
    """Update named avatar measurements and rebuild the mannequin.

    Args:
        **changes: Measurement names and replacement values in the avatar's units.

    Returns:
        The updated avatar feature.

    Raises:
        ValueError: If there is no active document or a measurement name is unknown.
    """
    import FreeCAD as App

    app = cast("_FreeCADApplication", App)

    doc = app.ActiveDocument
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


def set_avatar_pose(pose: str) -> _AvatarFeature:
    """Apply a named preset pose and rebuild the mannequin.

    Args:
        pose: Preset pose identifier supported by the avatar pose model.

    Returns:
        The updated avatar feature.

    Raises:
        ValueError: If there is no active document.
    """
    import FreeCAD as App

    app = cast("_FreeCADApplication", App)

    doc = app.ActiveDocument
    if doc is None:
        msg = "open a document before changing avatar pose"
        raise ValueError(msg)
    obj = _avatar(doc) or create_avatar()
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


def set_avatar_joint(
    bone: str, x: float = 0.0, y: float = 0.0, z: float = 0.0, *, mirror: bool = False
) -> object:
    """Persist one manual FK joint rotation and rebuild the mannequin.

    Args:
        bone: Skeleton bone identifier whose local rotation should change.
        x: Rotation component around the first local axis, in degrees.
        y: Rotation component around the second local axis, in degrees.
        z: Rotation component around the third local axis, in degrees.
        mirror: Whether the corresponding mirrored joint should also be updated.

    Returns:
        The rebuilt avatar feature.

    Raises:
        ValueError: If no document is active or the joint rotation is invalid.
    """
    import FreeCAD as App

    app = cast("_FreeCADApplication", App)

    doc = app.ActiveDocument
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


def set_avatar_provider(provider_id: str, source: object | None = None) -> _AvatarFeature:
    """Swap geometry providers without replacing the avatar object or garment links.

    Args:
        provider_id: Identifier of the geometry provider to activate.
        source: Optional source body required by the FreeCAD geometry provider.

    Returns:
        The updated avatar feature.

    Raises:
        ValueError: If no document is active or the provider/source is unsupported.
    """
    import FreeCAD as App

    app = cast("_FreeCADApplication", App)

    doc = app.ActiveDocument
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


def set_avatar_skin_offset(offset: float) -> _AvatarFeature:
    """Set the avatar's collision skin offset and rebuild the mannequin.

    Args:
        offset: New skin offset in millimetres.

    Returns:
        The updated avatar feature.

    Raises:
        ValueError: If no document is active or the resulting parameters are invalid.
    """
    import FreeCAD as App

    app = cast("_FreeCADApplication", App)

    doc = app.ActiveDocument
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


def avatar_measurement(name: str) -> float:
    """Read one saved avatar measurement by canonical measurement name.

    Args:
        name: Measurement key recognized by the avatar parameter model.

    Returns:
        The saved measurement value.

    Raises:
        ValueError: If no active avatar exists or the measurement name is unknown.
    """
    import FreeCAD as App

    app = cast("_FreeCADApplication", App)

    doc = app.ActiveDocument
    avatar = None if doc is None else _avatar(doc)
    if avatar is None:
        msg = "create a Cloth Avatar first"
        raise ValueError(msg)
    return _parameters(avatar).measurement(str(name))


def avatar_arrangement_points() -> object:
    """Return persisted local fitting points for the active avatar mesh.

    Returns:
        The fitting anchor records derived from the avatar's saved landmarks.

    Raises:
        ValueError: If there is no active avatar in the current document.
    """
    import FreeCAD as App

    app = cast("_FreeCADApplication", App)

    doc = app.ActiveDocument
    avatar = None if doc is None else _avatar(doc)
    if avatar is None:
        msg = "create a Cloth Avatar first"
        raise ValueError(msg)
    return arrangement_points_from_landmarks(avatar.Landmarks)


COMMANDS = list(AVATAR_COMMANDS)
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
    import FreeCADGui as gui
    from freecad_cloth.common import CommandAdapter as command_adapter
    command_adapter.register_commands(gui, _HANDLERS)
except (ImportError, AttributeError):
    pass
