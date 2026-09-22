"""Native FreeCAD Garment document hierarchy.

The FCStd document remains the persistence authority. This module only creates
native containers and links; domain objects remain authoritative.
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
    if getattr(obj, "SeamId", None) or sewing_type in {"SewingOperation", "SewingNetwork"} or _proxy_type(obj) in {"ClothSeam", "ClothSewingOperation", "ClothSewingNetwork"}:
        return "sewing"
    if str(getattr(obj, "FabricType", "")) == "FabricMaterial" or str(getattr(obj, "MaterialType", "")) == "Fabric":
        return "fabric"
    if str(getattr(obj, "FittingType", "")) in {"FittingScene", "ArrangementPoint", "BoundingVolume"}:
        return "fitting"
    name = str(getattr(obj, "Name", ""))
    if str(getattr(obj, "AvatarType", "")) == "ClothAvatar" or name == "AvatarCollision":
        return "avatar"
    if name in {"DrapeTarget", "ClothSimulation"} or name.startswith("DrapePanel") or str(getattr(obj, "ClothMeshType", "")) == "DrapedCloth" or _proxy_type(obj) == "ClothSimulation":
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
        if token not in seen[role]:
            seen[role].add(token); result[role].append(obj)
    return {role: tuple(sorted(items, key=lambda o: (str(getattr(o, "Label", "")), str(getattr(o, "Name", ""))))) for role, items in result.items()}

def get_garment(doc=None):
    if doc is None:
        import FreeCAD as App
        doc = App.ActiveDocument
    if doc is None:
        return None
    roots = [o for o in doc.Objects if str(getattr(o, "GarmentType", "")) == "ClothGarment"]
    if len(roots) > 1:
        raise ValueError("document contains multiple Cloth Garment roots")
    return roots[0] if roots else None

def _create_fabric_material(doc, fabric_group, root):
    material = next((o for o in getattr(fabric_group, "Group", ()) if str(getattr(o, "FabricType", "")) == "FabricMaterial"), None)
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

def _create_root(doc, name="Garment"):
    root = doc.addObject("App::DocumentObjectGroup", name)
    root.Label = "Garment"
    _prop(root, "App::PropertyString", "GarmentType", "Garment", "ClothGarment")
    _prop(root, "App::PropertyString", "SchemaVersion", "Garment", _SCHEMA_VERSION)
    _prop(root, "App::PropertyString", "GarmentId", "Garment", "garment:" + str(root.Name))
    for _key, group_name, label in GROUP_SPECS:
        group = doc.addObject("App::DocumentObjectGroup", "Garment" + group_name)
        group.Label = label
        _prop(group, "App::PropertyString", "GarmentGroup", "Garment", group_name)
        _prop(group, "App::PropertyString", "GarmentRootName", "Garment", root.Name)
        _prop(group, "App::PropertyLinkList", "Members", "Garment", [])
        root.addObject(group)
        _prop(root, "App::PropertyLink", group_name + "Group", "Garment", group)
    for name in ("PatternPieces","SewingObjects","FabricObjects","FittingObjects","AvatarObjects","SimulationObjects","Members"):
        _prop(root, "App::PropertyLinkList", name, "Garment", [])
    for name in ("PrimaryFabric","PrimaryFittingScene","PrimaryAvatar","PrimaryDrapeTarget","PrimarySimulation"):
        _prop(root, "App::PropertyLink", name, "Garment", None)
    _create_fabric_material(doc, root.FabricGroup, root)
    return root

def _ensure_root(root):
    doc = root.Document
    _prop(root, "App::PropertyString", "GarmentType", "Garment", "ClothGarment")
    _prop(root, "App::PropertyString", "SchemaVersion", "Garment", _SCHEMA_VERSION)
    if not str(getattr(root, "GarmentId", "")).strip():
        _prop(root, "App::PropertyString", "GarmentId", "Garment", "garment:" + str(root.Name))
    for _key, group_name, label in GROUP_SPECS:
        prop = group_name + "Group"
        group = getattr(root, prop, None)
        if group is None:
            group = doc.addObject("App::DocumentObjectGroup", "Garment" + group_name)
            group.Label = label
            root.addObject(group)
        _prop(group, "App::PropertyString", "GarmentGroup", "Garment", group_name)
        _prop(group, "App::PropertyString", "GarmentRootName", "Garment", root.Name)
        _prop(group, "App::PropertyLinkList", "Members", "Garment", [])
        _prop(root, "App::PropertyLink", prop, "Garment", group)
    for prop in ("PatternPieces","SewingObjects","FabricObjects","FittingObjects","AvatarObjects","SimulationObjects","Members"):
        _prop(root, "App::PropertyLinkList", prop, "Garment", [])
    for prop in ("PrimaryFabric","PrimaryFittingScene","PrimaryAvatar","PrimaryDrapeTarget","PrimarySimulation"):
        _prop(root, "App::PropertyLink", prop, "Garment", None)
    _create_fabric_material(doc, root.FabricGroup, root)

def _clear(group):
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
    root = garment or get_garment(doc) or _create_root(doc)
    if getattr(root, "Document", None) is not doc:
        raise ValueError("garment root belongs to a different FreeCAD document")
    if str(getattr(root, "GarmentType", "")) not in {"", "ClothGarment"}:
        raise ValueError("selected root is not a Cloth Garment container")
    _ensure_root(root)
    members = classify_members(o for o in doc.Objects if o is not root and str(getattr(o, "GarmentType", "")) != "ClothGarment")
    groups = {}
    for role, group_name, _label in GROUP_SPECS:
        group = getattr(root, group_name + "Group"); _clear(group); groups[role] = group
    for role, objects in members.items():
        for obj in objects: groups[role].addObject(obj)
        groups[role].Members = list(objects)
    root.PatternPieces = list(members["pattern"])
    root.SewingObjects = list(members["sewing"])
    root.FabricObjects = list(members["fabric"])
    root.FittingObjects = list(members["fitting"])
    root.AvatarObjects = list(members["avatar"])
    root.SimulationObjects = list(members["simulation"])
    root.Members = [o for role, _n, _l in GROUP_SPECS for o in members[role]]
    root.PrimaryFabric = _primary(members["fabric"], lambda o: str(getattr(o,"FabricType","")) == "FabricMaterial")
    root.PrimaryFittingScene = _primary(members["fitting"], lambda o: str(getattr(o,"FittingType","")) == "FittingScene")
    root.PrimaryAvatar = _primary(members["avatar"], lambda o: str(getattr(o,"AvatarType","")) == "ClothAvatar")
    root.PrimaryDrapeTarget = _primary(members["simulation"], lambda o: str(getattr(o,"Name","")) == "DrapeTarget")
    root.PrimarySimulation = _primary(members["simulation"], lambda o: str(getattr(o,"Name","")) == "ClothSimulation" or _proxy_type(o) == "ClothSimulation")
    doc.recompute()
    return root

def create_garment(doc=None, name="Garment"):
    if doc is None:
        import FreeCAD as App
        doc = App.ActiveDocument or App.newDocument("ClothGarment")
    return adopt_garment(doc, get_garment(doc) or _create_root(doc, name=name))
