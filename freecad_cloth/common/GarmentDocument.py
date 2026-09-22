"""Native FreeCAD Garment document hierarchy.

The FCStd document is the persistence authority.  This module only creates
native FreeCAD containers/links; it does not maintain a second project database.
Standalone object creation remains valid when no Garment root is present.
"""

GARMENT_SCHEMA_VERSION = "1"
GARMENT_ROOT_NAME = "Garment"
GARMENT_GROUPS = ("Patterns", "Sewing", "Fabric", "Avatar", "Simulation")
_ROLE_TO_GROUP = {
    "PatternPiece": "Patterns",
    "PatternSketch": "Patterns",
    "PatternMesh": "Patterns",
    "Seam": "Sewing",
    "SewingOperation": "Sewing",
    "SewingNetwork": "Sewing",
    "FabricMaterial": "Fabric",
    "Avatar": "Avatar",
    "AvatarCollision": "Avatar",
    "DrapeTarget": "Avatar",
    "Simulation": "Simulation",
    "SimulationOutput": "Simulation",
}


def _ensure_string(obj, name, group, value):
    if name not in getattr(obj, "PropertiesList", ()):
        obj.addProperty("App::PropertyString", name, group)
    setattr(obj, name, str(value))


def _ensure_link(obj, name, group, value=None):
    if name not in getattr(obj, "PropertiesList", ()):
        obj.addProperty("App::PropertyLink", name, group)
    if value is not None:
        setattr(obj, name, value)


def _children(container):
    return tuple(getattr(container, "Group", ()) or ())


def garment_root(doc):
    if doc is None:
        return None
    for obj in getattr(doc, "Objects", ()):
        if str(getattr(obj, "GarmentRole", "")) == "GarmentRoot":
            return obj
    candidate = getattr(doc, "getObject", lambda _name: None)(GARMENT_ROOT_NAME)
    if candidate is not None and str(getattr(candidate, "TypeId", "")) == "App::Part":
        return candidate
    return None


def garment_group(doc, role):
    root = garment_root(doc)
    if root is None:
        return None
    role = str(role)
    for child in _children(root):
        if str(getattr(child, "GarmentRole", "")) == role:
            return child
        if str(getattr(child, "Name", "")) == role and str(getattr(child, "TypeId", "")) == "App::DocumentObjectGroup":
            return child
    return None


def _ensure_group(doc, root, role):
    group = garment_group(doc, role)
    if group is None:
        group = doc.addObject("App::DocumentObjectGroup", role)
    _ensure_string(group, "GarmentRole", "Garment", role)
    _ensure_link(group, "Garment", "Garment", root)
    if group not in _children(root):
        root.addObject(group)
    return group


def ensure_fabric_material(doc, root=None):
    root = root or garment_root(doc)
    if root is None:
        return None
    fabric_group = garment_group(doc, "Fabric")
    if fabric_group is None:
        fabric_group = _ensure_group(doc, root, "Fabric")
    material = next(
        (
            obj for obj in _children(fabric_group)
            if str(getattr(obj, "GarmentRole", "")) == "FabricMaterial"
        ),
        None,
    )
    if material is None:
        material = doc.addObject("App::FeaturePython", "FabricMaterial")
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
    ):
        if name not in getattr(material, "PropertiesList", ()):
            material.addProperty("App::PropertyFloat", name, "Fabric")
            setattr(material, name, float(value))
    _ensure_link(material, "Garment", "Garment", root)
    if material not in _children(fabric_group):
        fabric_group.addObject(material)
    return material


def ensure_garment_hierarchy(doc, label="Garment"):
    """Create or repair the native Garment -> five-container hierarchy."""
    if doc is None:
        raise ValueError("a FreeCAD document is required")
    import FreeCAD as App  # noqa: F401

    root = garment_root(doc)
    if root is None:
        root = doc.addObject("App::Part", GARMENT_ROOT_NAME)
    root.Label = str(label or GARMENT_ROOT_NAME)
    _ensure_string(root, "GarmentRole", "Garment", "GarmentRoot")
    _ensure_string(root, "SchemaVersion", "Garment", GARMENT_SCHEMA_VERSION)

    for role in GARMENT_GROUPS:
        _ensure_group(doc, root, role)
    ensure_fabric_material(doc, root)
    doc.recompute()
    return root


def link_garment_object(obj, role, doc=None):
    """Link an existing object into the active native Garment hierarchy.

    This is intentionally a no-op for standalone documents so legacy creation
    paths retain their previous document shape.
    """
    if obj is None:
        return None
    doc = doc or getattr(obj, "Document", None)
    root = garment_root(doc)
    if root is None:
        return obj
    role = str(role)
    group_role = _ROLE_TO_GROUP.get(role, role if role in GARMENT_GROUPS else None)
    if group_role is None:
        raise ValueError("unsupported Garment hierarchy role: %s" % role)
    group = garment_group(doc, group_role)
    if group is None:
        group = _ensure_group(doc, root, group_role)
    _ensure_string(obj, "GarmentRole", "Garment", role)
    _ensure_link(obj, "Garment", "Garment", root)
    if obj not in _children(group):
        group.addObject(obj)
    return obj


def garment_structure(doc):
    """Return a deterministic native hierarchy snapshot for smoke evidence."""
    root = garment_root(doc)
    if root is None:
        raise ValueError("document has no native Garment root")
    structure = {
        "root": {"name": root.Name, "label": root.Label, "type": root.TypeId},
        "groups": {},
    }
    for role in GARMENT_GROUPS:
        group = garment_group(doc, role)
        if group is None:
            raise ValueError("missing Garment group: %s" % role)
        structure["groups"][role] = [
            {
                "name": obj.Name,
                "label": obj.Label,
                "type": obj.TypeId,
                "role": str(getattr(obj, "GarmentRole", "")),
            }
            for obj in sorted(_children(group), key=lambda item: str(item.Name))
        ]
    return structure


def create_garment_document(name="Garment", label="Garment"):
    """Create a production garment document with the complete native hierarchy."""
    import FreeCAD as App
    doc = App.newDocument(str(name))
    ensure_garment_hierarchy(doc, label)
    return doc
