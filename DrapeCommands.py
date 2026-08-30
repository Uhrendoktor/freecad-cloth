"""FreeCAD commands for selecting a persistent draping/collision target."""


def _selected_source():
    import FreeCADGui as Gui
    for obj in Gui.Selection.getSelection():
        if hasattr(obj, "Shape") or hasattr(obj, "Mesh"):
            return obj
    raise ValueError("select a FreeCAD shape or mesh as the drape target")


def _target(doc):
    return doc.getObject("DrapeTarget")


def create_drape_target_from_selection(deflection=1.0, thickness=2.0):
    """Create or replace the document's target from the current selection."""
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
    doc.recompute()
    return target


def create_mannequin_drape_target():
    """Create the default Cloth mannequin and make it the persistent target."""
    import FreeCAD as App
    from DrapeTarget import assign_drape_target, create_drape_target
    from SimulationObjects import create_humanoid_avatar

    doc = App.ActiveDocument or App.newDocument("ClothDrape")
    mannequin = doc.getObject("HumanoidAvatar") or create_humanoid_avatar(doc)
    target = _target(doc)
    if target is None:
        target = create_drape_target(doc, mannequin, "Mannequin", 1.0, 2.0)
    else:
        assign_drape_target(target, mannequin, "Mannequin")
    target.Label = "Drape Target (Mannequin)"
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


COMMANDS = [
    "ClothDrape_CreateTarget",
    "ClothDrape_CreateMannequinTarget",
    "ClothDrape_EnableTarget",
    "ClothDrape_DisableTarget",
]

_COMMAND_HANDLERS = {
    "ClothDrape_CreateTarget": create_drape_target_from_selection,
    "ClothDrape_CreateMannequinTarget": create_mannequin_drape_target,
    "ClothDrape_EnableTarget": lambda: set_drape_target_enabled(True),
    "ClothDrape_DisableTarget": lambda: set_drape_target_enabled(False),
}

_TOOLTIPS = {
    "ClothDrape_CreateTarget": "Use the selected FreeCAD shape or mesh as the persistent drape target",
    "ClothDrape_CreateMannequinTarget": "Create or select the Cloth mannequin as the drape target",
    "ClothDrape_EnableTarget": "Enable the persistent drape target",
    "ClothDrape_DisableTarget": "Disable the persistent drape target without clearing its source",
}


class _DrapeCommand:
    def __init__(self, function, active, tooltip):
        self.function, self.active, self.tooltip = function, active, tooltip

    def Activated(self):
        return self.function()

    def IsActive(self):
        return bool(self.active())

    def GetResources(self):
        return {"MenuText": self.function.__name__.replace("_", " ").title(), "ToolTip": self.tooltip}


try:
    import FreeCADGui as Gui
    for name, function in _COMMAND_HANDLERS.items():
        active = _has_source_selection if name == "ClothDrape_CreateTarget" else _has_document
        Gui.addCommand(name, _DrapeCommand(function, active, _TOOLTIPS[name]))
except (ImportError, AttributeError):
    pass
