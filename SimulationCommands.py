"""Commands for the Cloth Simulation workbench."""


def _drape_target_guard(target):
    """Return a stale-target status that must block proxy execution."""
    try:
        from DrapeTarget import target_status
        status = target_status(target)
    except (ImportError, AttributeError, TypeError, ValueError) as exc:
        return {"blocked": True, "state": "invalid", "message": "Cannot inspect drape target: %s" % exc,
                "stale": True, "reason": "target inspection failed"}
    blocked_states = {"stale", "unbuilt", "unassigned", "invalid", "missing"}
    return {"blocked": status["state"] in blocked_states, **status}


def _install_drape_target_recompute_guard():
    """Keep document recompute safe when a persistent target becomes stale."""
    try:
        from SimulationObjects import SimulationProxy
    except ImportError:
        return
    if getattr(SimulationProxy.execute, "_drape_target_guard", False):
        return
    original_execute = SimulationProxy.execute

    def guarded_execute(proxy, obj):
        target = getattr(obj, "DrapeTarget", None)
        if target is not None:
            status = _drape_target_guard(target)
            if status["blocked"]:
                obj.FiniteState = False
                return
        return original_execute(proxy, obj)

    guarded_execute._drape_target_guard = True
    SimulationProxy.execute = guarded_execute


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


def _require_drape_target_ready(doc):
    """Refuse solver advancement until the persistent collision target is current."""
    target = _find_drape_target(doc)
    status = _drape_target_guard(target)
    if status["state"] != "ready":
        raise RuntimeError(status["message"])
    return target


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


def simulate_selected(steps=None):
    """Advance the selected native simulation through its document proxy."""
    doc, scene = _require_simulation()
    _require_drape_target_ready(doc)
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
    target_info = _drape_target_guard(target)
    return {
        "state": "ready" if finite and not target_info["blocked"] else "invalid/stale",
        "message": "Cloth Simulation ready" if finite and not target_info["blocked"] else target_info["message"],
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
    _install_drape_target_recompute_guard()
    import FreeCADGui as Gui
    if hasattr(Gui, "addCommand"):
        Gui.addCommand("ClothSimulation_Create", _FunctionCommand(create_simulation, "Create Simulation", "Create a quality-aware cloth simulation object"))
        Gui.addCommand("ClothSimulation_CreateDrape", _FunctionCommand(create_drape_scene, "Create Drape Scene", "Create a deterministic cloth drape scene without implicit solver steps"))
        Gui.addCommand("ClothSimulation_Edit", _FunctionCommand(edit_simulation, "Simulation Controls", "Open the cloth simulation quality task panel"))
        Gui.addCommand("ClothSimulation_Step", _FunctionCommand(lambda: simulate_selected(), "Step Simulation", "Advance the quality-aware CPU cloth simulation", _has_simulation))
        Gui.addCommand("ClothSimulation_Run", _FunctionCommand(run_simulation, "Run Simulation", "Run 30 steps of the quality-aware CPU cloth simulation", _has_simulation))
        Gui.addCommand("ClothSimulation_Reset", _FunctionCommand(reset_simulation, "Reset Simulation", "Reset simulation state while retaining authored settings", _has_simulation))
except (ImportError, AttributeError):
    pass
