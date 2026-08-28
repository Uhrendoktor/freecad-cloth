"""Commands for the simulation workbench."""


def create_simulation():
    import FreeCAD as App
    doc = App.ActiveDocument or App.newDocument("ClothSimulation")
    obj = doc.addObject("App::FeaturePython", "ClothSimulation")
    obj.Label = "Cloth Simulation"
    obj.addProperty("App::PropertyString", "SolverBackend", "Simulation").SolverBackend = "NullSolver"
    obj.addProperty("App::PropertyFloat", "TimeStep", "Simulation").TimeStep = 0.01
    doc.recompute()


class _CreateSimulationCommand:
    def Activated(self):
        create_simulation()

    def GetResources(self):
        return {
            "MenuText": "Create Simulation",
            "ToolTip": "Create a cloth simulation document object",
        }


COMMANDS = ["ClothSimulation_Create"]

try:
    import FreeCADGui as Gui
    Gui.addCommand("ClothSimulation_Create", _CreateSimulationCommand())
except ImportError:
    pass
