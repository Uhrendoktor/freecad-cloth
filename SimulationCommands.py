"""Commands for the Cloth Simulation workbench."""

def create_simulation():
    import FreeCAD as App
    from SimulationQualityRuntimeV2 import create_quality_simulation_scene
    from SimulationMeshQuality import install_quality_mesh_patch
    install_quality_mesh_patch()
    doc=App.ActiveDocument or App.newDocument("ClothSimulation")
    return create_quality_simulation_scene(doc)

def create_drape_scene():
    import FreeCAD as App
    from SimulationObjects import create_simulation_scene
    doc=App.ActiveDocument or App.newDocument("ClothDrape")
    return create_simulation_scene(doc)

def _find_simulation(doc):
    return next((obj for obj in doc.Objects if getattr(obj,"TypeId","")=="App::FeaturePython" and getattr(obj,"Type","")=="ClothSimulation"),None)

def _find_drape_target(doc):
    return next((obj for obj in doc.Objects if getattr(obj,"Name","")=="DrapeTarget" or getattr(obj,"TargetType",None) is not None),None)

def edit_simulation():
    import FreeCAD as App
    from SimulationQualityGui import show_simulation_quality_task
    from SimulationQualityRuntimeV2 import ensure_quality_properties
    doc=App.ActiveDocument; scene=_find_simulation(doc) if doc else None
    if scene is not None: ensure_quality_properties(scene)
    return show_simulation_quality_task(scene)

def refresh_drape_target():
    import FreeCAD as App
    doc=App.ActiveDocument; target=_find_drape_target(doc) if doc else None
    if target is None: raise RuntimeError("no DrapeTarget in active document")
    from DrapeTarget import refresh_drape_target as refresh
    refresh(target)
    if doc is not None: doc.recompute()
    return target

def _require_simulation():
    import FreeCAD as App
    doc=App.ActiveDocument
    if doc is None: raise RuntimeError("no active document")
    scene=_find_simulation(doc)
    if scene is None: raise RuntimeError("no Cloth Simulation object in active document")
    return doc,scene

def _require_simulation_target_ready(doc):
    target=_find_drape_target(doc)
    if target is None: return None
    from DrapeTarget import target_status
    status=target_status(target)
    if status["lifecycle_state"] != "READY_FOR_SIMULATION":
        raise RuntimeError("DrapeTarget blocks simulation: %s (%s)"%(status["message"],status["reason"]))
    return target

def simulate_selected(steps=None):
    doc,scene=_require_simulation(); _require_simulation_target_ready(doc)
    count=int(steps if steps is not None else 1)
    if count<1: raise ValueError("steps must be positive")
    scene.Steps=int(scene.Steps)+count; doc.recompute()
    panels=tuple(getattr(scene,"DrapePanels",()))
    return panels[0] if panels else scene

def run_simulation(steps=30): return simulate_selected(steps)

def reset_simulation():
    doc,scene=_require_simulation(); _require_simulation_target_ready(doc)
    from SimulationObjects import reset_scene
    reset_scene(scene); scene.Document.recompute(); return scene

def simulation_status():
    try: doc,scene=_require_simulation()
    except RuntimeError as exc:
        return {"state":"unavailable","message":str(exc),"steps":0,"particles":0,"time":0.0,"target_state":"invalid","target_lifecycle_state":"INVALID","target_message":"No drape target selected","target_stale":True,"target_reason":"target missing"}
    finite=bool(getattr(scene,"FiniteState",True)); target=_find_drape_target(doc)
    try:
        from DrapeTarget import target_status
        target_info=target_status(target)
    except (ImportError,AttributeError,TypeError,ValueError) as exc:
        target_info={"state":"invalid","lifecycle_state":"INVALID","message":"Cannot inspect drape target: %s"%exc,"stale":True,"reason":"target inspection failed"}
    ready=finite and target_info["lifecycle_state"]=="READY_FOR_SIMULATION"
    return {"state":"ready" if ready else "invalid","message":"Cloth Simulation ready" if ready else "Cloth Simulation is blocked until the DrapeTarget is ready","steps":int(getattr(scene,"Steps",0)),"particles":int(getattr(scene,"ParticleCount",0)),"time":float(getattr(scene,"SimulatedTime",0.0)),"target_state":target_info["state"],"target_lifecycle_state":target_info["lifecycle_state"],"target_message":target_info["message"],"target_stale":bool(target_info["stale"]),"target_reason":target_info["reason"]}

class _FunctionCommand:
    def __init__(self,fn,text,tip,active=None): self.fn,self.text,self.tip,self.active=fn,text,tip,active
    def Activated(self): return self.fn()
    def GetResources(self): return {"MenuText":self.text,"ToolTip":self.tip}
    def IsActive(self): return bool(self.active()) if self.active is not None else True

def _has_simulation():
    try:
        import FreeCAD as App
        return bool(App.ActiveDocument and _find_simulation(App.ActiveDocument) is not None)
    except (ImportError,AttributeError): return False

COMMANDS=["ClothSimulation_Create","ClothSimulation_CreateDrape","ClothSimulation_Edit","ClothSimulation_RefreshDrapeTarget","ClothSimulation_Step","ClothSimulation_Run","ClothSimulation_Reset"]
try:
    import FreeCADGui as Gui
    if hasattr(Gui,"addCommand"):
        Gui.addCommand("ClothSimulation_Create",_FunctionCommand(create_simulation,"Create Simulation","Create a quality-aware cloth simulation object"))
        Gui.addCommand("ClothSimulation_CreateDrape",_FunctionCommand(create_drape_scene,"Create Drape Scene","Create a deterministic cloth drape scene"))
        Gui.addCommand("ClothSimulation_Edit",_FunctionCommand(edit_simulation,"Simulation Controls","Open the cloth simulation quality task panel"))
        Gui.addCommand("ClothSimulation_RefreshDrapeTarget",_FunctionCommand(refresh_drape_target,"Refresh Drape Target","Rebuild the persistent DrapeTarget collision surface"))
        Gui.addCommand("ClothSimulation_Step",_FunctionCommand(lambda:simulate_selected(),"Step Simulation","Advance simulation only when DrapeTarget is ready",_has_simulation))
        Gui.addCommand("ClothSimulation_Run",_FunctionCommand(run_simulation,"Run Simulation","Run simulation only when DrapeTarget is ready",_has_simulation))
        Gui.addCommand("ClothSimulation_Reset",_FunctionCommand(reset_simulation,"Reset Simulation","Reset simulation state",_has_simulation))
except (ImportError,AttributeError): pass
