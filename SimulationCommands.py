"""Commands for the Cloth Simulation workbench."""


def create_simulation():
    import FreeCAD as App
    from SimulationQualityRuntimeV2 import create_quality_simulation_scene
    from SimulationMeshQuality import install_quality_mesh_patch
    install_quality_mesh_patch()
    doc = App.ActiveDocument or App.newDocument("ClothSimulation")
    return create_quality_simulation_scene(doc)


def create_drape_scene():
    import FreeCAD as App
    from SimulationObjects import create_simulation_scene
    # Creation is intentionally side-effect-light. Simulation advances only
    # through explicit Step/Run controls so command invocation is predictable.
    doc = App.ActiveDocument or App.newDocument("ClothDrape")
    return create_simulation_scene(doc)


def _find_simulation(doc):
    return next((obj for obj in doc.Objects if getattr(obj, "TypeId", "") == "App::FeaturePython"
                 and getattr(obj, "Type", "") == "ClothSimulation"), None)


def edit_simulation():
    """Open the native simulation quality controls task panel."""
    import FreeCAD as App
    from SimulationQualityGui import show_simulation_quality_task
    from SimulationQualityRuntimeV2 import ensure_quality_properties
    doc = App.ActiveDocument
    scene = _find_simulation(doc) if doc else None
    if scene is not None:
        ensure_quality_properties(scene)
    return show_simulation_quality_task(scene)


def simulate_selected(steps=None):
    """Advance the selected native simulation through its document proxy."""
    import FreeCAD as App
    doc = App.ActiveDocument
    if doc is None:
        raise RuntimeError("no active document")
    scene = _find_simulation(doc)
    if scene is None:
        scene = create_simulation()
    count = int(steps if steps is not None else 1)
    if count < 1:
        raise ValueError("steps must be positive")
    scene.Steps = int(scene.Steps) + count
    doc.recompute()
    panels = tuple(getattr(scene, "DrapePanels", ()))
    return panels[0] if panels else scene


class _FunctionCommand:
    def __init__(self, fn, text, tip): self.fn, self.text, self.tip = fn, text, tip
    def Activated(self): self.fn()
    def GetResources(self): return {"MenuText": self.text, "ToolTip": self.tip}


COMMANDS = [
    "ClothSimulation_Create",
    "ClothSimulation_CreateDrape",
    "ClothSimulation_Edit",
    "ClothSimulation_Step",
]

try:
    import FreeCADGui as Gui
    if hasattr(Gui, "addCommand"):
        Gui.addCommand("ClothSimulation_Create", _FunctionCommand(create_simulation, "Create Simulation", "Create a quality-aware cloth simulation object"))
        Gui.addCommand("ClothSimulation_CreateDrape", _FunctionCommand(create_drape_scene, "Create Drape Scene", "Create a deterministic cloth drape scene without implicit solver steps"))
        Gui.addCommand("ClothSimulation_Edit", _FunctionCommand(edit_simulation, "Simulation Controls", "Open the cloth simulation quality task panel"))
        Gui.addCommand("ClothSimulation_Step", _FunctionCommand(lambda: simulate_selected(), "Step Simulation", "Advance the quality-aware CPU cloth simulation"))
except (ImportError, AttributeError):
    pass
