"""Commands for the Cloth Simulation workbench."""


def create_simulation():
    import FreeCAD as App
    doc = App.ActiveDocument or App.newDocument("ClothSimulation")
    obj = doc.addObject("App::FeaturePython", "ClothSimulation")
    obj.Label = "Cloth Simulation"
    obj.addProperty("App::PropertyString", "SolverBackend", "Simulation").SolverBackend = "XPBDClothSolver"
    obj.addProperty("App::PropertyFloat", "TimeStep", "Simulation").TimeStep = 0.01
    obj.addProperty("App::PropertyInteger", "Iterations", "Simulation").Iterations = 8
    obj.addProperty("App::PropertyInteger", "Steps", "Simulation").Steps = 1
    obj.addProperty("App::PropertyLink", "SourceMesh", "Simulation")
    obj.addProperty("App::PropertyLink", "ResultMesh", "Simulation")
    doc.recompute()
    return obj


def create_drape_scene():
    import FreeCAD as App
    from SimulationObjects import create_drape_scene as _create
    doc = App.ActiveDocument or App.newDocument("ClothDrape")
    return _create(doc)


def edit_simulation():
    """Open the simulation controls task panel."""
    import FreeCADGui as Gui
    scene = next((o for o in Gui.ActiveDocument.Document.Objects if hasattr(o, "FiniteState") and hasattr(o, "Steps")), None) if Gui.ActiveDocument else None
    from SimulationGui import show_simulation_task
    show_simulation_task(scene)


def simulate_selected(steps=None):
    import FreeCAD as App
    from PatternMesh import TriangleMesh
    from SimulationScene import SimulationScene
    doc = App.ActiveDocument
    if doc is None: raise RuntimeError("no active document")
    simulation = next((o for o in doc.Objects if getattr(o, "SolverBackend", "") == "XPBDClothSolver"), None)
    source = getattr(simulation, "SourceMesh", None) if simulation else None
    if source is None: source = next((o for o in doc.Objects if getattr(o, "ClothMeshType", "") == "PatternSurface"), None)
    if source is None: raise RuntimeError("create a pattern mesh before starting simulation")
    vertices = tuple((float(v.x), float(v.y)) for v in source.Mesh.Points)
    triangles = tuple(tuple(int(i) for i in facet) for facet in source.Mesh.Facets)
    mesh = TriangleMesh(vertices, triangles, tuple(range(len(vertices))))
    scene = SimulationScene.from_mesh(mesh, iterations=getattr(simulation, "Iterations", 8))
    scene.step_many(int(steps if steps is not None else getattr(simulation, "Steps", 1)), float(getattr(simulation, "TimeStep", 0.01)))
    result = getattr(simulation, "ResultMesh", None) if simulation else None
    if result is None:
        result = doc.addObject("Mesh::Feature", "DrapedCloth"); result.Label = "Draped Cloth"
        result.addProperty("App::PropertyString", "ClothMeshType", "Cloth").ClothMeshType = "SimulationResult"
        if simulation: simulation.ResultMesh = result
    import Mesh
    native = Mesh.Mesh()
    for a, b, c in mesh.triangles:
        pa, pb, pc = scene.state.positions[a], scene.state.positions[b], scene.state.positions[c]
        native.addFacet(App.Vector(*pa), App.Vector(*pb), App.Vector(*pc))
    result.Mesh = native
    if simulation: simulation.SourceMesh = source
    doc.recompute(); return result


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
        Gui.addCommand("ClothSimulation_Create", _FunctionCommand(create_simulation, "Create Simulation", "Create a cloth simulation object"))
        Gui.addCommand("ClothSimulation_CreateDrape", _FunctionCommand(create_drape_scene, "Create Drape Scene", "Create a deterministic two-panel cloth drape scene"))
        Gui.addCommand("ClothSimulation_Edit", _FunctionCommand(edit_simulation, "Simulation Controls", "Open the cloth simulation task panel"))
        Gui.addCommand("ClothSimulation_Step", _FunctionCommand(lambda: simulate_selected(), "Step Simulation", "Advance the reference XPBD cloth simulation"))
except (ImportError, AttributeError):
    pass
