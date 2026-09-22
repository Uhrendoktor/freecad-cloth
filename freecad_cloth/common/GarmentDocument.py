"""Native FreeCAD Garment document hierarchy.

The FCStd document remains the persistence authority. This module only creates
native containers and links; it does not introduce a second project database.
"""

from __future__ import annotations

from typing import Any, Iterable

GROUP_SPECS = (
    ("pattern", "Patterns", "Patterns"),
    ("sewing", "Sewing", "Sewing"),
    ("fabric", "Fabric", "Fabric"),
    ("fitting", "Fitting", "Fitting / Arrangement"),
    ("avatar", "Avatar", "Avatar"),
    ("simulation", "Simulation", "Simulation"),
)
_SCHEMA_VERSION = "1"


def _prop(obj: Any, kind: str, name: str, group: str, value: Any = None) -> None:
    if not hasattr(obj, name):
        obj.addProperty(kind, name, group)
    if value is not None:
        setattr(obj, name, value)


def _proxy_type(obj: Any) -> str:
    return str(getattr(getattr(obj, "Proxy", None), "Type", ""))


def classify_object(obj: Any) -> str | None:
    if str(getattr(obj, "PatternType", "")) == "PatternPiece":
        return "pattern"
    sewing_type = str(getattr(obj, "SewingType", ""))
    if (
        getattr(obj, "SeamId", None)
        or sewing_type in {"SewingOperation", "SewingNetwork"}
        or _proxy_type(obj) in {"ClothSeam", "ClothSewingOperation", "ClothSewingNetwork"}
    ):
        return "sewing"
    fabric_type = str(getattr(obj, "FabricType", ""))
    material_type = str(getattr(obj, "MaterialType", ""))
    if fabric_type == "FabricMaterial" or material_type == "Fabric":
        return "fabric"
    fitting_type = str(getattr(obj, "FittingType", ""))
    if fitting_type in {"FittingScene", "ArrangementPoint", "BoundingVolume"}:
        return "fitting"
    name = str(getattr(obj, "Name", ""))
    if str(getattr(obj, "AvatarType", "")) == "ClothAvatar" or name in {"DrapeTarget", "AvatarCollision"}:
        return "avatar"
    cloth_mesh_type = str(getattr(obj, "ClothMeshType", ""))
    if (
        name == "ClothSimulation"
        or name.startswith("DrapePanel")
        or cloth_mesh_type == "DrapedCloth"
        or _proxy_type(obj) == "ClothSimulation"
    ):
        return "simulation"
    return None


def classify_members(objects: Iterable[Any]) -> dict[str, tuple[Any, ...]]:
    result = {key: [] for key, _name, _label in GROUP_SPECS}
    seen = {key: set() for key, _name, _label in GROUP_SPECS}
    for obj in objects:
        role = classify_object(obj)
        if role is None:
            continue
        token = str(getattr(obj, "Name", "")).strip() or str(id(obj))
        if token in seen[role]:
            continue
        seen[role].add(token)
        result[role].append(obj)
    return {
        role: tuple(sorted(items, key=lambda item: (
            str(getattr(item, "Label", "")),
            str(getattr(item, "Name", "")),
        )))
        for role, items in result.items()
    }


def get_garment(doc=None):
    if doc is None:
        import FreeCAD as App
        doc = App.ActiveDocument
    if doc is None:
        return None
    roots = [obj for obj in doc.Objects if str(getattr(obj, "GarmentType", "")) == "ClothGarment"]
    if len(roots) > 1:
        raise ValueError("document contains multiple Cloth Garment roots")
    return roots[0] if roots else None


def _create_fabric_material(doc, fabric_group, root):
    material = next(
        (obj for obj in getattr(fabric_group, "Group", ())
         if str(getattr(obj, "FabricType", "")) == "FabricMaterial"),
        None,
    )
    if material is None:
        material = doc.addObject("App::FeaturePython", "FabricMaterial")
        material.Label = "Fabric Material"
    _prop(material, "App::PropertyString", "FabricType", "Fabric", "FabricMaterial")
    _prop(material, "App::PropertyString", "MaterialType", "Fabric", "Fabric")
    _prop(material, "App::PropertyString", "MaterialId", "Fabric", "fabric-default")
    _prop(material, "App::PropertyString", "MaterialName", "Fabric", "Default Fabric")
    _prop(material, "App::PropertyLink", "Garment", "Garment", root)
    if material not in getattr(fabric_group, "Group", ()):
        fabric_group.addObject(material)
    return material


def _create_root(doc, name: str = "Garment"):
    if doc is None:
        raise ValueError("a FreeCAD document is required")
    root = doc.addObject("App::DocumentObjectGroup", name)
    root.Label = "Garment"
    _prop(root, "App::PropertyString", "GarmentType", "Garment", "ClothGarment")
    _prop(root, "App::PropertyString", "SchemaVersion", "Garment", _SCHEMA_VERSION)
    _prop(root, "App::PropertyString", "GarmentId", "Garment", "garment:" + str(root.Name))
    for _key, group_name, label in GROUP_SPECS:
        subgroup = doc.addObject("App::DocumentObjectGroup", "Garment" + group_name)
        subgroup.Label = label
        _prop(subgroup, "App::PropertyString", "GarmentGroup", "Garment", group_name)
        _prop(subgroup, "App::PropertyString", "GarmentRootName", "Garment", root.Name)
        _prop(subgroup, "App::PropertyLinkList", "Members", "Garment", [])
        root.addObject(subgroup)
        _prop(root, "App::PropertyLink", group_name + "Group", "Garment", subgroup)
    for name in (
        "PatternPieces", "SewingObjects", "FabricObjects",
        "FittingObjects", "AvatarObjects", "SimulationObjects", "Members",
    ):
        _prop(root, "App::PropertyLinkList", name, "Garment", [])
    for name in ("PrimaryFabric", "PrimaryFittingScene", "PrimaryAvatar", "PrimaryDrapeTarget", "PrimarySimulation"):
        _prop(root, "App::PropertyLink", name, "Garment", None)
    _create_fabric_material(doc, getattr(root, "FabricGroup"), root)
    return root


def _ensure_root_properties(root):
    _prop(root, "App::PropertyString", "GarmentType", "Garment", "ClothGarment")
    _prop(root, "App::PropertyString", "SchemaVersion", "Garment", _SCHEMA_VERSION)
    if not str(getattr(root, "GarmentId", "")).strip():
        _prop(root, "App::PropertyString", "GarmentId", "Garment", "garment:" + str(root.Name))
    doc = root.Document
    for _key, group_name, label in GROUP_SPECS:
        prop = group_name + "Group"
        group = getattr(root, prop, None)
        if group is None:
            group = doc.addObject("App::DocumentObjectGroup", "Garment" + group_name)
            group.Label = label
            _prop(group, "App::PropertyString", "GarmentGroup", "Garment", group_name)
            _prop(group, "App::PropertyString", "GarmentRootName", "Garment", root.Name)
            root.addObject(group)
            _prop(root, "App::PropertyLink", prop, "Garment", group)
        _prop(group, "App::PropertyString", "GarmentGroup", "Garment", group_name)
        _prop(group, "App::PropertyString", "GarmentRootName", "Garment", root.Name)
        if "Garment" in getattr(group, "PropertiesList", ()):
            try:
                group.removeProperty("Garment")
            except Exception:
                pass
        _prop(group, "App::PropertyLinkList", "Members", "Garment", [])
    for prop in (
        "PatternPieces", "SewingObjects", "FabricObjects",
        "FittingObjects", "AvatarObjects", "SimulationObjects", "Members",
    ):
        _prop(root, "App::PropertyLinkList", prop, "Garment", [])
    for prop in ("PrimaryFabric", "PrimaryFittingScene", "PrimaryAvatar", "PrimaryDrapeTarget", "PrimarySimulation"):
        _prop(root, "App::PropertyLink", prop, "Garment", None)
    _create_fabric_material(doc, getattr(root, "FabricGroup"), root)


def _clear_group(group) -> None:
    for member in tuple(getattr(group, "Group", ()) or ()):
        group.removeObject(member)


def _primary(items, predicate):
    return next((obj for obj in items if predicate(obj)), None)


def adopt_garment(doc=None, garment=None):
    if doc is None:
        import FreeCAD as App
        doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a FreeCAD document before adopting a garment")
    root = garment or get_garment(doc)
    if root is None:
        root = _create_root(doc)
    elif getattr(root, "Document", None) is not doc:
        raise ValueError("garment root belongs to a different FreeCAD document")
    elif str(getattr(root, "GarmentType", "")) not in {"", "ClothGarment"}:
        raise ValueError("selected root is not a Cloth Garment container")
    _ensure_root_properties(root)
    members = classify_members(
        obj for obj in doc.Objects
        if obj is not root and str(getattr(obj, "GarmentType", "")) != "ClothGarment"
    )
    role_groups = {}
    for role, group_name, _label in GROUP_SPECS:
        group = getattr(root, group_name + "Group")
        _clear_group(group)
        role_groups[role] = group
    for role, objects in members.items():
        group = role_groups[role]
        for obj in objects:
            group.addObject(obj)
        group.Members = list(objects)
    root.PatternPieces = list(members["pattern"])
    root.SewingObjects = list(members["sewing"])
    root.FabricObjects = list(members["fabric"])
    root.FittingObjects = list(members["fitting"])
    root.AvatarObjects = list(members["avatar"])
    root.SimulationObjects = list(members["simulation"])
    root.Members = [obj for role, _group_name, _label in GROUP_SPECS for obj in members[role]]
    root.PrimaryFabric = _primary(members["fabric"], lambda obj: str(getattr(obj, "FabricType", "")) == "FabricMaterial")
    root.PrimaryFittingScene = _primary(members["fitting"], lambda obj: str(getattr(obj, "FittingType", "")) == "FittingScene")
    root.PrimaryAvatar = _primary(members["avatar"], lambda obj: str(getattr(obj, "AvatarType", "")) == "ClothAvatar")
    root.PrimaryDrapeTarget = _primary(members["avatar"], lambda obj: str(getattr(obj, "Name", "")) == "DrapeTarget")
    root.PrimarySimulation = _primary(
        members["simulation"],
        lambda obj: str(getattr(obj, "Name", "")) == "ClothSimulation" or _proxy_type(obj) == "ClothSimulation",
    )
    doc.recompute()
    return root


def create_garment(doc=None, name: str = "Garment"):
    if doc is None:
        import FreeCAD as App
        doc = App.ActiveDocument or App.newDocument("ClothGarment")
    root = get_garment(doc)
    if root is None:
        root = _create_root(doc, name=name)
    return adopt_garment(doc, root)
