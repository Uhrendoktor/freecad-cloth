"""FreeCAD commands for selecting and editing a persistent draping/collision target."""


def _selected_source():
    import FreeCADGui as Gui
    for obj in Gui.Selection.getSelection():
        if hasattr(obj, "Shape") or hasattr(obj, "Mesh"):
            return obj
    raise ValueError("select a FreeCAD shape or mesh as the drape target")


def _target(doc):
    return doc.getObject("DrapeTarget")


def _attach_to_simulation(doc, source, target):
    from SimulationObjects import set_avatar_collision_source
    scenes = [o for o in doc.Objects if getattr(o, "Type", "") == "ClothSimulation"]
    for scene in scenes:
        proxy = set_avatar_collision_source(scene, source, float(target.CollisionThickness), float(target.CollisionDeflection))
        scene.AvatarProxy = proxy
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
    _attach_to_simulation(doc, source, target)
    doc.recompute()
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
    _attach_to_simulation(doc, mannequin, target)
    doc.recompute()
    return target


def edit_drape_target():
    """Open the native task panel for the current persistent DrapeTarget."""
    import FreeCAD as App
    from DrapeGui import show_drape_target_task
    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("create a document before editing the drape target")
    target = _target(doc)
    if target is None:
        raise ValueError("create a drape target first")
    return show_drape_target_task(target)


def refresh_drape_target():
    """Rebuild the collision metadata from the persistent target source."""
    import FreeCAD as App
    from DrapeTarget import refresh_drape_target
    doc = App.ActiveDocument
    if doc is None or _target(doc) is None:
        raise ValueError("create a drape target first")
    target = refresh_drape_target(_target(doc))
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


def show_diagnostics():
    """Open post-simulation stress/strain/fit/pressure diagnostics."""
    import FreeCAD as App
    from ClothDiagnosticsGui import show_diagnostics as show_panel
    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("create a simulation before opening diagnostics")
    return show_panel()


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


COMMANDS = [
    "ClothDrape_CreateTarget",
    "ClothDrape_CreateMannequinTarget",
    "ClothDrape_EditTarget",
    "ClothDrape_RefreshTarget",
    "ClothDrape_EnableTarget",
    "ClothDrape_DisableTarget",
    "ClothDrape_Diagnostics",
]
_HANDLERS = {
    "ClothDrape_CreateTarget": create_drape_target_from_selection,
    "ClothDrape_CreateMannequinTarget": create_mannequin_drape_target,
    "ClothDrape_EditTarget": edit_drape_target,
    "ClothDrape_RefreshTarget": refresh_drape_target,
    "ClothDrape_EnableTarget": lambda: set_drape_target_enabled(True),
    "ClothDrape_DisableTarget": lambda: set_drape_target_enabled(False),
    "ClothDrape_Diagnostics": show_diagnostics,
}
_TOOLTIPS = {
    "ClothDrape_CreateTarget": "Use the selected FreeCAD shape or mesh as the persistent drape target",
    "ClothDrape_CreateMannequinTarget": "Create or select the Cloth mannequin as the drape target",
    "ClothDrape_EditTarget": "Edit the persistent drape target and collision quality settings",
    "ClothDrape_RefreshTarget": "Rebuild collision geometry from the current drape target source",
    "ClothDrape_EnableTarget": "Enable the persistent drape target",
    "ClothDrape_DisableTarget": "Disable the persistent drape target without clearing its source",
    "ClothDrape_Diagnostics": "Analyze simulated cloth with stress, strain, fit, and pressure maps",
}


class _DrapeCommand:
    def __init__(self, function, active, tooltip):
        self.function, self.active, self.tooltip = function, active, tooltip

    def Activated(self):
        return self.function()

    def IsActive(self):
        return bool(self.active())

    def GetResources(self):
        labels = {
            "edit_drape_target": "Edit Drape Target",
            "refresh_drape_target": "Refresh Drape Target",
            "show_diagnostics": "Cloth Diagnostics",
        }
        label = labels.get(self.function.__name__, self.function.__name__.replace("_", " ").title())
        return {"MenuText": label, "ToolTip": self.tooltip}


try:
    import FreeCADGui as Gui
    for name, function in _HANDLERS.items():
        active = _has_source_selection if name == "ClothDrape_CreateTarget" else _has_document
        Gui.addCommand(name, _DrapeCommand(function, active, _TOOLTIPS[name]))
except (ImportError, AttributeError):
    pass
