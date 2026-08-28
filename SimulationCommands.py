"""Initial commands for the simulation workbench."""

def create_simulation():
    import FreeCAD as App
    doc = App.ActiveDocument or App.newDocument("ClothSimulation")
    obj = doc.addObject("App::FeaturePython", "ClothSimulation")
    obj.Label = "Cloth Simulation"
    obj.addProperty("App::PropertyString", "SolverBackend", "Simulation").SolverBackend = "NullSolver"
    obj.addProperty("App::PropertyFloat", "TimeStep", "Simulation").TimeStep = 0.01
    doc.recompute()


COMMANDS = ["ClothSimulation_Create"]

try:
    import FreeCADGui as Gui
    Gui.addCommand("ClothSimulation_Create", create_simulation)
except ImportError:
    pass
