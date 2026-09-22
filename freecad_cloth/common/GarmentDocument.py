def _doc_object(doc, name):
    getter = getattr(doc, "getObject", None)
    if callable(getter):
        return getter(name)
    return next((obj for obj in tuple(getattr(doc, "Objects", ())) if getattr(obj, "Name", "") == name), None)


"""Native FreeCAD garment hierarchy adapter.

The hierarchy groups existing authoritative document objects. It never creates
duplicates and does not store a second semantic model.
"""
GROUP_NAMES = ("Patterns", "Sewing", "Fabric", "Fitting", "Avatar", "Simulation")
GROUP_OBJECT_NAMES = {name: "Garment" + name for name in GROUP_NAMES}


def garment_domain(obj):
    pattern_type = str(getattr(obj, "PatternType", ""))
    sewing_type = str(getattr(obj, "SewingType", ""))
    avatar_type = str(getattr(obj, "AvatarType", ""))
    target_type = str(getattr(obj, "TargetType", ""))
    name = str(getattr(obj, "Name", ""))
    if pattern_type == "PatternPiece" or name.startswith("Sketch") or name.endswith("_Mesh"):
        return "Patterns"
    if getattr(obj, "SeamId", "") or sewing_type in {"SewingNetwork", "SewingOperation"}:
        return "Sewing"
    if avatar_type == "ClothAvatar" or name in {"AvatarCollision", "HumanoidAvatar"}:
        return "Avatar"
    if name == "DrapeTarget" or target_type:
        return "Fitting"
    if str(getattr(getattr(obj, "Proxy", None), "Type", "")) == "ClothSimulation":
        return "Simulation"
    return None


def ensure_garment_structure(doc):
    """Return the native Garment root and its six stable child groups."""
    root = _doc_object(doc, "Garment")
    if root is None:
        root = doc.addObject("App::Part", "Garment")
        root.Label = "Garment"
    if "GarmentType" not in getattr(root, "PropertiesList", ()):
        root.addProperty("App::PropertyString", "GarmentType", "Garment")
    root.GarmentType = "Garment"
    if "SchemaVersion" not in getattr(root, "PropertiesList", ()):
        root.addProperty("App::PropertyString", "SchemaVersion", "Garment")
    root.SchemaVersion = "1"

    groups = {}
    for domain in GROUP_NAMES:
        name = GROUP_OBJECT_NAMES[domain]
        group = _doc_object(doc, name)
        if group is None:
            group = doc.addObject("App::DocumentObjectGroup", name)
            group.Label = domain
        if group not in tuple(getattr(root, "Group", ())):
            root.addObject(group)
        groups[domain] = group

    for obj in tuple(getattr(doc, "Objects", ())):
        if obj is root or obj in groups.values():
            continue
        domain = garment_domain(obj)
        if domain is None:
            continue
        group = groups[domain]
        if obj not in tuple(getattr(group, "Group", ())):
            group.addObject(obj)
    return root, groups


def register_garment_object(doc, obj, domain=None):
    root, groups = ensure_garment_structure(doc)
    domain = domain or garment_domain(obj)
    if domain not in groups:
        raise ValueError("unsupported Garment hierarchy domain: %s" % domain)
    group = groups[domain]
    if obj is not root and obj not in tuple(getattr(group, "Group", ())):
        group.addObject(obj)
    return obj