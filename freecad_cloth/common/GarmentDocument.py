# Copyright (C) 2026 FreeCAD Cloth contributors
"""Native FreeCAD Garment document hierarchy.

The FCStd document is the persistence authority. This module only creates native
FreeCAD containers and links; it does not maintain a second project database.
Standalone object creation remains valid when no Garment root is present.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from types import ModuleType
from typing import Protocol, TypedDict, cast

GARMENT_SCHEMA_VERSION = "1"
GARMENT_ROOT_NAME = "Garment"
GARMENT_GROUPS: tuple[str, ...] = ("Patterns", "Sewing", "Fabric", "Avatar", "Simulation")
_ROLE_TO_GROUP: dict[str, str] = {
    "PatternPiece": "Patterns",
    "PatternSketch": "Patterns",
    "PatternMesh": "Patterns",
    "Seam": "Sewing",
    "SewingOperation": "Sewing",
    "SewingNetwork": "Sewing",
    "FabricMaterial": "Fabric",
    "Avatar": "Avatar",
    "DrapeTarget": "Avatar",
    "Simulation": "Simulation",
    "SimulationOutput": "Simulation",
}


class FreeCADDocumentObjectProtocol(Protocol):
    """Native FreeCAD object identity and property capabilities used by the hierarchy adapter."""

    Name: str
    Label: str
    TypeId: str
    PropertiesList: list[str]


class _FreeCADContainer(FreeCADDocumentObjectProtocol, Protocol):
    """Native Part/group capabilities required to contain garment objects."""

    Group: list[FreeCADDocumentObjectProtocol]


class _FreeCADDocument(Protocol):
    """Document operations used by the garment hierarchy adapter."""

    Objects: list[FreeCADDocumentObjectProtocol]

    def recompute(self) -> None:
        """Recompute the document after hierarchy changes."""
        ...


class _FreeCADApplication(Protocol):
    """Application operation needed to create a new FreeCAD document."""

    def new_document(self, name: str) -> _FreeCADDocument:
        """Create a document using its internal name.

        Args:
            name: Internal document name requested by the caller.

        Returns:
            Newly created FreeCAD document.
        """
        ...


class _GarmentRootSnapshot(TypedDict):
    """JSON-compatible identity fields describing the native Garment root."""

    name: str
    label: str
    type: str


class _GarmentChildSnapshot(TypedDict):
    """JSON-compatible identity fields describing a garment group child."""

    name: str
    label: str
    type: str
    role: str


class _GarmentStructure(TypedDict):
    """JSON-compatible snapshot returned by the garment hierarchy inspector."""

    root: _GarmentRootSnapshot
    groups: dict[str, list[_GarmentChildSnapshot]]


def _add_property(
    obj: FreeCADDocumentObjectProtocol,
    property_type: str,
    name: str,
    group: str,
) -> None:
    """Add a property through the native FreeCAD runtime method.

    Args:
        obj: FreeCAD object receiving the new property.
        property_type: Native FreeCAD property type identifier.
        name: Persisted property name to register.
        group: Property-editor group that should contain the property.
    """
    add_property = cast(
        Callable[[str, str, str], FreeCADDocumentObjectProtocol],
        getattr(obj, "addProperty"),
    )
    add_property(property_type, name, group)


def _new_document_object(
    doc: _FreeCADDocument,
    object_type: str,
    name: str,
) -> FreeCADDocumentObjectProtocol:
    """Create a native document object using FreeCAD's runtime API.

    Args:
        doc: FreeCAD document that will own the new object.
        object_type: Native object type identifier such as App::Part.
        name: Internal document name assigned to the new object.

    Returns:
        The created FreeCAD document object.
    """
    add_object = cast(
        Callable[[str, str], FreeCADDocumentObjectProtocol],
        getattr(doc, "addObject"),
    )
    return add_object(object_type, name)


def _add_child(container: _FreeCADContainer, child: FreeCADDocumentObjectProtocol) -> None:
    """Add a document object to a native container.

    Args:
        container: FreeCAD group or Part receiving the child.
        child: Document object to add to the container.
    """
    add_child = cast(
        Callable[[FreeCADDocumentObjectProtocol], None],
        getattr(container, "addObject"),
    )
    add_child(child)


def _recompute_document(doc: _FreeCADDocument) -> None:
    """Recompute the document after its persisted hierarchy changes.

    Args:
        doc: FreeCAD document containing the updated garment hierarchy.
    """
    doc.recompute()


def _ensure_string(
    obj: FreeCADDocumentObjectProtocol,
    name: str,
    group: str,
    value: str,
) -> None:
    """Ensure a string property exists and stores the normalized value.

    Args:
        obj: FreeCAD object receiving the property value.
        name: Persisted property name to create or update.
        group: Property-editor group used when adding the property.
        value: Value converted to its string representation.
    """
    if name not in getattr(obj, "PropertiesList", ()):
        _add_property(obj, "App::PropertyString", name, group)
    setattr(obj, name, str(value))


def _children(container: _FreeCADContainer) -> tuple[FreeCADDocumentObjectProtocol, ...]:
    """Return the objects currently stored in a native group or Part.

    Args:
        container: FreeCAD container exposing its Group sequence.

    Returns:
        A tuple snapshot of the container's current child objects.
    """
    return tuple(container.Group)


def garment_root(doc: _FreeCADDocument | None) -> _FreeCADContainer | None:
    """Find the native Garment root without creating a document hierarchy.

    Args:
        doc: FreeCAD document to inspect, or None if no document is active.

    Returns:
        The existing Garment root, or None when the document has no root.
    """
    if doc is None:
        return None
    for obj in doc.Objects:
        if str(getattr(obj, "GarmentRole", "")) == "GarmentRoot":
            return cast("_FreeCADContainer", obj)
    for obj in doc.Objects:
        if obj.Name == GARMENT_ROOT_NAME and obj.TypeId == "App::Part":
            return cast("_FreeCADContainer", obj)
    return None


def garment_group(doc: _FreeCADDocument | None, role: str) -> _FreeCADContainer | None:
    """Find an existing native Garment group by its persisted role.

    Args:
        doc: FreeCAD document containing the garment hierarchy.
        role: Stable group role, such as Patterns, Sewing, or Avatar.

    Returns:
        The matching group, or None when the root or group is absent.
    """
    root = garment_root(doc)
    if root is None:
        return None
    group_role = str(role)
    for child in _children(root):
        if str(getattr(child, "GarmentRole", "")) == group_role:
            return cast("_FreeCADContainer", child)
        if child.Name == group_role and child.TypeId == "App::DocumentObjectGroup":
            return cast("_FreeCADContainer", child)
    return None


def _ensure_group(
    doc: _FreeCADDocument,
    root: _FreeCADContainer,
    role: str,
) -> _FreeCADContainer:
    """Create a Garment group if needed and ensure its root link is present.

    Args:
        doc: FreeCAD document that owns the group.
        root: Native Garment root receiving the group.
        role: Stable group role and internal document name.

    Returns:
        The existing or newly created group for the requested role.
    """
    group = garment_group(doc, role)
    if group is None:
        group = cast(
            "_FreeCADContainer",
            _new_document_object(doc, "App::DocumentObjectGroup", role),
        )
    _ensure_string(group, "GarmentRole", "Garment", role)
    if group not in _children(root):
        _add_child(root, group)
    return group


def ensure_fabric_material(
    doc: _FreeCADDocument,
    root: _FreeCADContainer | None = None,
) -> FreeCADDocumentObjectProtocol | None:
    """Ensure the default fabric material object exists inside the Fabric group.

    Args:
        doc: FreeCAD document that owns the hierarchy and material.
        root: Optional existing Garment root; looked up from the document by default.

    Returns:
        The default fabric material object, or None when no Garment root exists.
    """
    root = root or garment_root(doc)
    if root is None:
        return None
    fabric_group = garment_group(doc, "Fabric")
    if fabric_group is None:
        fabric_group = _ensure_group(doc, root, "Fabric")
    material = next(
        (
            obj
            for obj in _children(fabric_group)
            if str(getattr(obj, "GarmentRole", "")) == "FabricMaterial"
        ),
        None,
    )
    if material is None:
        material = _new_document_object(doc, "App::FeaturePython", "FabricMaterial")
        material.Label = "Fabric Material"
    _ensure_string(material, "GarmentRole", "Garment", "FabricMaterial")
    _ensure_string(material, "MaterialType", "Fabric", "Fabric")
    _ensure_string(material, "MaterialId", "Fabric", "fabric-default")
    _ensure_string(material, "MaterialName", "Fabric", "Default Fabric")
    for name, value in (
        ("Density", 150.0),
        ("Thickness", 0.5),
        ("Stretch", 0.02),
        ("Shear", 0.02),
        ("Bend", 0.01),
        ("Friction", 0.5),
        ("Specular", 0.25),
        ("Roughness", 0.65),
        ("Transparency", 0.0),
    ):
        if name not in getattr(material, "PropertiesList", ()):
            _add_property(material, "App::PropertyFloat", name, "Fabric")
            setattr(material, name, float(value))
    if "Color" not in getattr(material, "PropertiesList", ()):
        _add_property(material, "App::PropertyColor", "Color", "Presentation")
        set_color = cast(
            Callable[[str, tuple[float, float, float]], None],
            getattr(material, "__setattr__"),
        )
        set_color("Color", (0.72, 0.34, 0.46))
    if material not in _children(fabric_group):
        _add_child(fabric_group, material)
    return material


def ensure_garment_hierarchy(
    doc: _FreeCADDocument | None,
    label: str = "Garment",
) -> _FreeCADContainer:
    """Create or repair the native Garment root and its five standard groups.

    Args:
        doc: FreeCAD document that will own the hierarchy.
        label: User-facing root label, with Garment used for an empty value.

    Returns:
        The native Garment root after all standard groups and the default material exist.

    Raises:
        ValueError: If no FreeCAD document is supplied.
    """
    if doc is None:
        msg = "a FreeCAD document is required"
        raise ValueError(msg)

    root = garment_root(doc)
    if root is None:
        root = cast(
            "_FreeCADContainer",
            _new_document_object(doc, "App::Part", GARMENT_ROOT_NAME),
        )
    root.Label = str(label or GARMENT_ROOT_NAME)
    _ensure_string(root, "GarmentRole", "Garment", "GarmentRoot")
    _ensure_string(root, "SchemaVersion", "Garment", GARMENT_SCHEMA_VERSION)

    for role in GARMENT_GROUPS:
        _ensure_group(doc, root, role)
    ensure_fabric_material(doc, root)
    _recompute_document(doc)
    return root


def link_garment_object(
    obj: FreeCADDocumentObjectProtocol | None,
    role: str,
    doc: _FreeCADDocument | None = None,
) -> FreeCADDocumentObjectProtocol | None:
    """Link an existing object into the native Garment group for its role.

    This is intentionally a no-op when no Garment root exists, keeping
    standalone object creation a first-class workflow.

    Args:
        obj: Existing FreeCAD document object to link.
        role: Persisted object role used to select a Garment group.
        doc: Optional owning document; inferred from the object when omitted.

    Returns:
        The original object, or None when no object was supplied.

    Raises:
        ValueError: If the role does not map to a supported Garment group.
    """
    if obj is None:
        return None
    if doc is None:
        doc = cast("_FreeCADDocument | None", getattr(obj, "Document", None))
    if doc is None:
        return obj
    root = garment_root(doc)
    if root is None:
        return obj
    object_role = str(role)
    group_role = _ROLE_TO_GROUP.get(
        object_role,
        object_role if object_role in GARMENT_GROUPS else None,
    )
    if group_role is None:
        msg = f"unsupported Garment hierarchy role: {object_role}"
        raise ValueError(msg)
    group = garment_group(doc, group_role)
    if group is None:
        group = _ensure_group(doc, root, group_role)
    _ensure_string(obj, "GarmentRole", "Garment", object_role)
    if obj not in _children(group):
        _add_child(group, obj)
    return obj


def garment_structure(doc: _FreeCADDocument) -> _GarmentStructure:
    """Return a deterministic hierarchy snapshot for smoke evidence.

    Args:
        doc: FreeCAD document whose native Garment hierarchy should be inspected.

    Returns:
        A mapping with root identity and sorted child records for all five groups.

    Raises:
        ValueError: If the document has no Garment root or a standard group is missing.
    """
    root = garment_root(doc)
    if root is None:
        msg = "document has no native Garment root"
        raise ValueError(msg)
    root_snapshot: _GarmentRootSnapshot = {
        "name": root.Name,
        "label": root.Label,
        "type": root.TypeId,
    }
    groups: dict[str, list[_GarmentChildSnapshot]] = {}
    for role in GARMENT_GROUPS:
        group = garment_group(doc, role)
        if group is None:
            msg = f"missing Garment group: {role}"
            raise ValueError(msg)
        groups[role] = [
            {
                "name": obj.Name,
                "label": obj.Label,
                "type": obj.TypeId,
                "role": str(getattr(obj, "GarmentRole", "")),
            }
            for obj in sorted(_children(group), key=lambda item: item.Name)
        ]
    return {"root": root_snapshot, "groups": groups}


def create_garment_document(
    name: str = "Garment",
    label: str = "Garment",
    *,
    app_module: _FreeCADApplication | ModuleType | None = None,
) -> _FreeCADDocument:
    """Create a new FreeCAD document with the complete native garment hierarchy.

    Args:
        name: Internal FreeCAD document name.
        label: User-facing label for the Garment root.
        app_module: Optional injected application adapter or native FreeCAD module.

    Returns:
        The newly created document after its root, groups, and default material exist.

    Raises:
        ImportError: If the FreeCAD application module is not loaded or injected.
    """
    runtime_module = app_module
    if runtime_module is None:
        loaded_module = sys.modules.get("FreeCAD")
        if loaded_module is None:
            msg = "FreeCAD must be loaded or supplied as app_module to create a document"
            raise ImportError(msg)
        runtime_module = loaded_module
    if isinstance(runtime_module, ModuleType):
        create_document = cast(
            Callable[[str], _FreeCADDocument],
            getattr(runtime_module, "newDocument"),
        )
        doc = create_document(str(name))
    else:
        doc = runtime_module.new_document(str(name))
    ensure_garment_hierarchy(doc, label)
    return doc
