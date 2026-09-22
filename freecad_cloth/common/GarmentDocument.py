"""Native FreeCAD garment document hierarchy contract.

The garment container is a document-level organization layer only. Existing
PatternPiece, sewing, fitting, avatar, DrapeTarget, and ClothSimulation
objects remain authoritative; this module creates native FreeCAD groups and
link properties that reference those objects without cloning their data.
"""

from __future__ import annotations

from typing import Any, Iterable


GROUP_SPECS = (
    ("pattern", "Pattern", "Pattern"),
    ("sewing", "Sewing", "Sewing"),
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
    """Return the garment hierarchy role for an existing document object."""
    pattern_type = str(getattr(obj, "PatternType", ""))
    if pattern_type == "PatternPiece":
        return "pattern"

    sewing_type = str(getattr(obj, "SewingType", ""))
    if (
        getattr(obj, "SeamId", None)
        or sewing_type in {"SewingOperation", "SewingNetwork"}
        or _proxy_type(obj) in {"ClothSeam", "ClothSewingOperation", "ClothSewingNetwork"}
    ):
        return "sewing"

    fitting_type = str(getattr(obj, "FittingType", ""))
    if fitting_type in {"FittingScene", "ArrangementPoint", "BoundingVolume"}:
        return "fitting"

    if str(getattr(obj, "AvatarType", "")) == "ClothAvatar":
        return "avatar"

    name = str(getattr(obj, "Name", ""))
    cloth_mesh_type = str(getattr(obj, "ClothMeshType", ""))
    if (
        name == "DrapeTarget"
        or name == "ClothSimulation"
        or name.startswith("DrapePanel")
        or name == "AvatarCollision"
        or cloth_mesh_type == "DrapedCloth"
        or _proxy_type(obj) == "ClothSimulation"
    ):
        return "simulation"

    return None


def classify_members(objects: Iterable[Any]) -> dict[str, tuple[Any, ...]]:
    """Classify document objects into deterministic garment roles."""
    result = {key: [] for key, _name, _label in GROUP_SPECS}
    for obj in objects:
        role = classify_object(obj)
        if role is not None:
            result[role].append(obj)

    for role in result:
        result[role] = tuple(
            sorted(
                result[role],
                key=lambda item: (
                    str(getattr(item, "Label", "")),
                    str(getattr(item, "Name", "")),
                ),
            )
        )
    return result


def get_garment(doc=None):
    """Return the single native garment root in *doc*, if one exists."""
    if doc is None:
        import FreeCAD as App
        doc = App.ActiveDocument
    if doc is None:
        return None
    roots = [
        obj
        for obj in doc.Objects
        if str(getattr(obj, "GarmentType", "")) == "ClothGarment"
    ]
    if len(roots) > 1:
        raise ValueError("document contains multiple Cloth Garment roots")
    return roots[0] if roots else None


def _create_root(doc, name: str = "Garment"):
    if doc is None:
        raise ValueError("a FreeCAD document is required")
    root = doc.addObject("App::DocumentObjectGroup", name)
    root.Label = "Garment"
    _prop(root, "App::PropertyString", "GarmentType", "Garment", "ClothGarment")
    _prop(root, "App::PropertyString", "SchemaVersion", "Garment", _SCHEMA_VERSION)
    _prop(root, "App::PropertyString", "GarmentId", "Garment", "garment:" + str(root.Name))
    for key, group_name, label in GROUP_SPECS:
        subgroup = doc.addObject("App::DocumentObjectGroup", "Garment" + group_name)
        subgroup.Label = label
        _prop(subgroup, "App::PropertyString", "GarmentGroup", "Garment", group_name)
        _prop(subgroup, "App::PropertyLink", "Garment", "Garment", root)
        root.addObject(subgroup)
        _prop(root, "App::PropertyLink", group_name + "Group", "Garment", subgroup)
        _prop(subgroup, "App::PropertyLinkList", "Members", "Garment", [])
    for name in (
        "PatternPieces",
        "SewingObjects",
        "FittingObjects",
        "AvatarObjects",
        "SimulationObjects",
    ):
        _prop(root, "App::PropertyLinkList", name, "Garment", [])
    for name in ("PrimaryFittingScene", "PrimaryAvatar", "PrimaryDrapeTarget", "PrimarySimulation"):
        _prop(root, "App::PropertyLink", name, "Garment", None)
    _prop(root, "App::PropertyLinkList", "Members", "Garment", [])
    return root


def _ensure_root_properties(root):
    _prop(root, "App::PropertyString", "GarmentType", "Garment", "ClothGarment")
    _prop(root, "App::PropertyString", "SchemaVersion", "Garment", _SCHEMA_VERSION)
    if not str(getattr(root, "GarmentId", "")).strip():
        _prop(root, "App::PropertyString", "GarmentId", "Garment", "garment:" + str(root.Name))
    for key, group_name, label in GROUP_SPECS:
        name = group_name + "Group"
        group = getattr(root, name, None)
        if group is None:
            doc = root.Document
            group = doc.addObject("App::DocumentObjectGroup", "Garment" + group_name)
            group.Label = label
            _prop(group, "App::PropertyString", "GarmentGroup", "Garment", group_name)
            _prop(group, "App::PropertyLink", "Garment", "Garment", root)
            root.addObject(group)
            _prop(root, "App::PropertyLink", name, "Garment", group)
        _prop(group, "App::PropertyString", "GarmentGroup", "Garment", group_name)
        _prop(group, "App::PropertyLink", "Garment", "Garment", root)
        _prop(group, "App::PropertyLinkList", "Members", "Garment", [])
    for prop in (
        "PatternPieces",
        "SewingObjects",
        "FittingObjects",
        "AvatarObjects",
        "SimulationObjects",
        "Members",
    ):
        _prop(root, "App::PropertyLinkList", prop, "Garment", [])
    for prop in ("PrimaryFittingScene", "PrimaryAvatar", "PrimaryDrapeTarget", "PrimarySimulation"):
        _prop(root, "App::PropertyLink", prop, "Garment", None)


def _clear_group(group) -> None:
    for member in tuple(getattr(group, "Group", ()) or ()):
        group.removeObject(member)


def _primary(members, predicate):
    for obj in members:
        if predicate(obj):
            return obj
    return None


def adopt_garment(doc=None, garment=None):
    """Create or reconcile the native hierarchy around existing document objects.

    No domain object is cloned or rewritten. The operation only updates native
    FreeCAD group membership and Link/LinkList properties.
    """
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
        obj
        for obj in doc.Objects
        if obj is not root and str(getattr(obj, "GarmentType", "")) != "ClothGarment"
    )

    role_groups = {}
    for role, group_name, _label in GROUP_SPECS:
        group = getattr(root, group_name + "Group")
        _clear_group(group)
        group.addObject(group)
        role_groups[role] = group

    for role, objects in members.items():
        group = role_groups[role]
        group.addObjects(list(objects))
        group.Members = list(objects)

    root.PatternPieces = list(members["pattern"])
    root.SewingObjects = list(members["sewing"])
    root.FittingObjects = list(members["fitting"])
    root.AvatarObjects = list(members["avatar"])
    root.SimulationObjects = list(members["simulation"])
    root.Members = [
        obj
        for role, _group_name, _label in GROUP_SPECS
        for obj in members[role]
    ]

    root.PrimaryFittingScene = _primary(
        members["fitting"], lambda obj: str(getattr(obj, "FittingType", "")) == "FittingScene"
    )
    root.PrimaryAvatar = _primary(
        members["avatar"], lambda obj: str(getattr(obj, "AvatarType", "")) == "ClothAvatar"
    )
    root.PrimaryDrapeTarget = _primary(
        members["simulation"], lambda obj: str(getattr(obj, "Name", "")) == "DrapeTarget"
    )
    root.PrimarySimulation = _primary(
        members["simulation"],
        lambda obj: str(getattr(obj, "Name", "")) == "ClothSimulation"
        or _proxy_type(obj) == "ClothSimulation",
    )

    doc.recompute()
    return root


def create_garment(doc=None, name: str = "Garment"):
    """Create the single public garment container and adopt existing objects."""
    if doc is None:
        import FreeCAD as App
        doc = App.ActiveDocument or App.newDocument("ClothGarment")
    existing = get_garment(doc)
    if existing is not None:
        return adopt_garment(doc, existing)

    root = _create_root(doc, name=name)
    return adopt_garment(doc, root)
