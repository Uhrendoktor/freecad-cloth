"""FreeCAD commands for selecting a persistent draping/collision target."""


def _selected_source():
    import FreeCADGui as Gui
    for obj in Gui.Selection.getSelection():
        if hasattr(obj, "Shape") or hasattr(obj, "Mesh"):
            return obj
    raise ValueError("select a FreeCAD shape or mesh as the drape target")


def _target(doc):
    return doc.getObject("DrapeTarget")


def _attach_to_simulation(doc, target):
    scenes = [o for o in doc.Objects if getattr(o, "Type", "") == "ClothSimulation"]
    for scene in scenes:
        scene.DrapeTarget = target
    doc.recompute()


def create_drape_target_from_selection(deflection=1.0, thickness=2.0):
    import FreeCAD as App
    from DrapeTarget import assign_drape_target, create_drape_target
    doc = App.ActiveDocument or App.newDocument("ClothDrape")
    source = _selected_source()
    target = _target(doc)
    if target is None:
        target = create_drape_target(doc, source, "FreeCAD Geometry", deflection, thickness)
    else:
        target.CollisionDeflection = float(deflection)
        target.CollisionThickness = float(thickness)
        assign_drape_target(target, source, "FreeCAD Geometry")
    _attach_to_simulation(doc, target)
    return target


def create_mannequin_drape_target():
    import FreeCAD as App
    from AvatarCommands import create_avatar
    from DrapeTarget import assign_drape_target, create_drape_target
    doc = App.ActiveDocument or App.newDocument("ClothDrape")
    mannequin = doc.getObject("ClothAvatar") or create_avatar()
    target = _target(doc)
    if target is None:
        target = create_drape_target(doc, mannequin, "Mannequin", 1.0, 2.0)
    else:
        assign_drape_target(target, mannequin, "Mannequin")
    target.Label = "Drape Target (Mannequin)"
    _attach_to_simulation(doc, target)
    return target


def refresh_drape_target():
    import FreeCAD as App
    from DrapeTarget import refresh_drape_target as refresh
    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before refreshing the drape target")
    target = _target(doc)
    if target is None:
        raise ValueError("create a drape target first")
    refresh(target)
    doc.recompute()
    return target


def set_drape_target_enabled(enabled=True):
    import FreeCAD as App
    doc = App.ActiveDocument
    if doc is None or _target(doc) is None:
        raise ValueError("create a drape target first")
    target = _target(doc)
    target.Enabled = bool(enabled)
    doc.recompute()
    return target


def _has_document():
    try:
        import FreeCAD as App
        return App.ActiveDocument is not None
    except ImportError:
        return False


def _has_source_selection():
    try:
        _selected_source()
        return True
    except (ImportError, ValueError):
        return False


def _has_target():
    try:
        import FreeCAD as App
        return bool(App.ActiveDocument and _target(App.ActiveDocument) is not None)
    except (ImportError, AttributeError):
        return False


COMMANDS = [
    "ClothDrape_CreateTarget",
    "ClothDrape_CreateMannequinTarget",
    "ClothDrape_RefreshTarget",
    "ClothDrape_EnableTarget",
    "ClothDrape_DisableTarget",
]
_COMMAND_HANDLERS = {
    "ClothDrape_CreateTarget": create_drape_target_from_selection,
    "ClothDrape_CreateMannequinTarget": create_mannequin_drape_target,
    "ClothDrape_RefreshTarget": refresh_drape_target,
    "ClothDrape_EnableTarget": lambda: set_drape_target_enabled(True),
    "ClothDrape_DisableTarget": lambda: set_drape_target_enabled(False),
}
_TOOLTIPS = {
    "ClothDrape_CreateTarget": "Use the selected FreeCAD shape or mesh as the persistent drape target",
    "ClothDrape_CreateMannequinTarget": "Create or select the Cloth mannequin as the drape target",
    "ClothDrape_RefreshTarget": "Rebuild the persistent collision surface after the target changes",
    "ClothDrape_EnableTarget": "Enable the persistent drape target",
    "ClothDrape_DisableTarget": "Disable the persistent drape target without clearing its source",
}
class _DrapeCommand:
    def __init__(self, function, active, tooltip): self.function, self.active, self.tooltip = function, active, tooltip
    def Activated(self): return self.function()
    def IsActive(self): return bool(self.active())
    def GetResources(self): return {"MenuText": self.function.__name__.replace("_", " ").title(), "ToolTip": self.tooltip}
try:
    import FreeCADGui as Gui
    _ACTIVATION = {
        "ClothDrape_CreateTarget": _has_source_selection,
        "ClothDrape_CreateMannequinTarget": _has_document,
        "ClothDrape_RefreshTarget": _has_target,
        "ClothDrape_EnableTarget": _has_target,
        "ClothDrape_DisableTarget": _has_target,
    }
    for name, function in _COMMAND_HANDLERS.items():
        Gui.addCommand(name, _DrapeCommand(function, _ACTIVATION[name], _TOOLTIPS[name]))
except (ImportError, AttributeError):
    pass
