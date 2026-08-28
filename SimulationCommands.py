"""Commands for the simulation workbench."""


def create_simulation():
    """Create a simulation object from the first available cloth mesh."""
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


def simulate_selected(steps=None):
    """Run the reference XPBD solver on a selected PatternMesh object."""
    import FreeCAD as App
    from PatternMesh import TriangleMesh
    from SimulationScene import SimulationScene

    doc = App.ActiveDocument
    if doc is None:
        raise RuntimeError("no active document")
    simulation = next((o for o in doc.Objects if getattr(o, "SolverBackend", "") == "XPBDClothSolver"), None)
    source = getattr(simulation, "SourceMesh", None) if simulation else None
    if source is None:
        source = next((o for o in doc.Objects if getattr(o, "ClothMeshType", "") == "PatternSurface"), None)
    if source is None:
        raise RuntimeError("create a pattern mesh before starting simulation")
    vertices = tuple((float(v.x), float(v.y)) for v in source.Mesh.Points)
    triangles = tuple(tuple(int(i) for i in facet) for facet in source.Mesh.Facets)
    mesh = TriangleMesh(vertices, triangles, tuple(range(len(vertices))))
    scene = SimulationScene.from_mesh(mesh, iterations=getattr(simulation, "Iterations", 8))
    scene.step_many(int(steps if steps is not None else getattr(simulation, "Steps", 1)), float(getattr(simulation, "TimeStep", 0.01)))

    result = getattr(simulation, "ResultMesh", None) if simulation else None
    if result is None:
        result = doc.addObject("Mesh::Feature", "DrapedCloth")
        result.Label = "Draped Cloth"
        result.addProperty("App::PropertyString", "ClothMeshType", "Cloth").ClothMeshType = "SimulationResult"
        if simulation:
            simulation.ResultMesh = result
    import Mesh
    native = Mesh.Mesh()
    for a, b, c in mesh.triangles:
        pa, pb, pc = scene.state.positions[a], scene.state.positions[b], scene.state.positions[c]
        native.addFacet(App.Vector(*pa), App.Vector(*pb), App.Vector(*pc))
    result.Mesh = native
    if simulation:
        simulation.SourceMesh = source
    doc.recompute()
    return result


class _CreateSimulationCommand:
    def Activated(self):
        create_simulation()

    def GetResources(self):
        return {
            "MenuText": "Create Simulation",
            "ToolTip": "Create a cloth simulation object",
        }


class _SimulateCommand:
    def Activated(self):
        simulate_selected()

    def GetResources(self):
        return {
            "MenuText": "Step Simulation",
            "ToolTip": "Advance the reference XPBD cloth simulation",
        }


COMMANDS = ["ClothSimulation_Create", "ClothSimulation_Step"]

try:
    import FreeCADGui as Gui
    Gui.addCommand("ClothSimulation_Create", _CreateSimulationCommand())
    Gui.addCommand("ClothSimulation_Step", _SimulateCommand())
except ImportError:
    pass
