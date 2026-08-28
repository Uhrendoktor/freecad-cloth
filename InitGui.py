class ClothPatternWorkbench:
    MenuText = "Cloth Pattern"
    ToolTip = "Parametric sewing-pattern design"

    def Initialize(self):
        import PatternCommands
        self.commands = PatternCommands.COMMANDS
        self.appendToolbar("Cloth Pattern", self.commands)
        self.appendMenu("Cloth Pattern", self.commands)

    def Activated(self):
        return None

    def Deactivated(self):
        return None

    def ContextMenu(self, recipient):
        if recipient in ("view", "tree"):
            self.appendContextMenu("Cloth Pattern", self.commands)

    def GetClassName(self):
        return "Gui::PythonWorkbench"


class ClothSimulationWorkbench:
    MenuText = "Cloth Simulation"
    ToolTip = "3D cloth assembly and simulation"

    def Initialize(self):
        import SimulationCommands
        self.commands = SimulationCommands.COMMANDS
        self.appendToolbar("Cloth Simulation", self.commands)
        self.appendMenu("Cloth Simulation", self.commands)

    def Activated(self):
        return None

    def Deactivated(self):
        return None

    def ContextMenu(self, recipient):
        if recipient in ("view", "tree"):
            self.appendContextMenu("Cloth Simulation", self.commands)

    def GetClassName(self):
        return "Gui::PythonWorkbench"


try:
    import FreeCADGui as Gui
    Gui.addWorkbench(ClothPatternWorkbench())
    Gui.addWorkbench(ClothSimulationWorkbench())
except ImportError:
    # Allows static imports/tests outside FreeCAD.
    Gui = None
