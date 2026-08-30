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
    # through explicit Step/Run/Reset controls so command invocation is predictable.
    doc = App.ActiveDocument or App.newDocument("ClothDrape")
    return create_simulation_scene(doc)


def _find_simulation(doc):
    return next((obj for obj in doc.Objects if getattr(obj, "TypeId", "") == "App::FeaturePython"
                 and getattr(obj, "Type", "") == "ClothSimulation"), None)


def _find_drape_target(doc):
    return next((obj for obj in doc.Objects if getattr(obj, "Name", "") == "DrapeTarget"
                 or getattr(obj, "TargetType", None) is not None), None)


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


def _require_simulation():
    import FreeCAD as App
    doc = App.ActiveDocument
    if doc is None:
        raise RuntimeError("no active document")
    scene = _find_simulation(doc)
    if scene is None:
        raise RuntimeError("no Cloth Simulation object in active document")
    return doc, scene


def _require_target_ready(doc):
    target = _find_drape_target(doc)
    try:
        from DrapeTarget import target_status
        status = target_status(target)
    except (ImportError, AttributeError, TypeError, ValueError) as exc:
        raise RuntimeError("Cannot inspect drape target: %s" % exc)
    if status["state"] != "ready":
        raise RuntimeError(status["message"])
    return target


def simulate_selected(steps=None):
    """Advance the selected native simulation through its document proxy."""
    doc, scene = _require_simulation()
    _require_target_ready(doc)
    count = int(steps if steps is not None else 1)
    if count < 1:
        raise ValueError("steps must be positive")
    scene.Steps = int(scene.Steps) + count
    doc.recompute()
    panels = tuple(getattr(scene, "DrapePanels", ()))
    return panels[0] if panels else scene


def run_simulation(steps=30):
    """Run an explicit batch of simulation steps on the active scene."""
    return simulate_selected(steps)


def reset_simulation():
    """Reset the active simulation state without changing its authored settings."""
    _doc, scene = _require_simulation()
    from SimulationObjects import reset_scene
    reset_scene(scene)
    scene.Document.recompute()
    return scene


def simulation_status():
    """Return a deterministic, UI-friendly lifecycle/status summary."""
    try:
        doc, scene = _require_simulation()
    except RuntimeError as exc:
        return {"state": "unavailable", "message": str(exc), "steps": 0, "particles": 0, "time": 0.0,
                "target_state": "missing", "target_message": "No drape target selected", "target_stale": True,
                "target_reason": "target missing"}
    finite = bool(getattr(scene, "FiniteState", True))
    target = _find_drape_target(doc)
    try:
        from DrapeTarget import target_status
        target_info = target_status(target)
    except (ImportError, AttributeError, TypeError, ValueError) as exc:
        target_info = {"state": "invalid", "message": "Cannot inspect drape target: %s" % exc, "stale": True,
                       "reason": "target inspection failed"}
    return {
        "state": "ready" if finite else "invalid/non-finite",
        "message": "Cloth Simulation ready" if finite else "Cloth Simulation has invalid/non-finite state",
        "steps": int(getattr(scene, "Steps", 0)),
        "particles": int(getattr(scene, "ParticleCount", 0)),
        "time": float(getattr(scene, "SimulatedTime", 0.0)),
        "target_state": target_info["state"],
        "target_message": target_info["message"],
        "target_stale": bool(target_info["stale"]),
        "target_reason": target_info["reason"],
    }


class _FunctionCommand:
    def __init__(self, fn, text, tip, active=None):
        self.fn, self.text, self.tip, self.active = fn, text, tip, active

    def Activated(self):
        return self.fn()

    def GetResources(self):
        return {"MenuText": self.text, "ToolTip": self.tip}

    def IsActive(self):
        return bool(self.active()) if self.active is not None else True


def _simulation_can_step():
    try:
        import FreeCAD as App
        doc = App.ActiveDocument
        if not doc or _find_simulation(doc) is None:
            return False
        target = _find_drape_target(doc)
        from DrapeTarget import target_status
        return target_status(target)["state"] == "ready"
    except (ImportError, AttributeError, TypeError, ValueError):
        return False


def _has_simulation():
    try:
        import FreeCAD as App
        return bool(App.ActiveDocument and _find_simulation(App.ActiveDocument) is not None)
    except (ImportError, AttributeError):
        return False


COMMANDS = [
    "ClothSimulation_Create",
    "ClothSimulation_CreateDrape",
    "ClothSimulation_Edit",
    "ClothSimulation_Step",
    "ClothSimulation_Run",
    "ClothSimulation_Reset",
]

try:
    import FreeCADGui as Gui
    if hasattr(Gui, "addCommand"):
        Gui.addCommand("ClothSimulation_Create", _FunctionCommand(create_simulation, "Create Simulation", "Create a quality-aware cloth simulation object"))
        Gui.addCommand("ClothSimulation_CreateDrape", _FunctionCommand(create_drape_scene, "Create Drape Scene", "Create a deterministic cloth drape scene without implicit solver steps"))
        Gui.addCommand("ClothSimulation_Edit", _FunctionCommand(edit_simulation, "Simulation Controls", "Open the cloth simulation quality task panel"))
        Gui.addCommand("ClothSimulation_Step", _FunctionCommand(lambda: simulate_selected(), "Step Simulation", "Advance the quality-aware CPU cloth simulation", _simulation_can_step))
        Gui.addCommand("ClothSimulation_Run", _FunctionCommand(run_simulation, "Run Simulation", "Run 30 steps of the quality-aware CPU cloth simulation", _simulation_can_step))
        Gui.addCommand("ClothSimulation_Reset", _FunctionCommand(reset_simulation, "Reset Simulation", "Reset simulation state while retaining authored settings", _has_simulation))
except (ImportError, AttributeError):
    pass
