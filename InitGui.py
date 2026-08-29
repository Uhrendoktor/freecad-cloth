try:
    import FreeCADGui as Gui
except ImportError:
    Gui = None


if Gui is not None:
    class ClothPatternWorkbench(Gui.Workbench):
        MenuText = "Cloth Pattern"
        ToolTip = "Parametric sewing-pattern design"
        def Initialize(self):
            import PatternCommands
            import PatternMarks
            self.commands = PatternCommands.COMMANDS + PatternMarks.COMMANDS
            self.appendToolbar("Cloth Pattern", self.commands)
            self.appendMenu("Cloth Pattern", self.commands)
        def Activated(self): return None
        def Deactivated(self): return None
        def ContextMenu(self, recipient):
            if recipient in ("view", "tree"): self.appendContextMenu("Cloth Pattern", self.commands)
        def GetClassName(self): return "Gui::PythonWorkbench"


    class ClothSimulationWorkbench(Gui.Workbench):
        MenuText = "Cloth Simulation"
        ToolTip = "3D cloth assembly and simulation"
        def Initialize(self):
            import SimulationCommands
            self.commands = SimulationCommands.COMMANDS
            self.appendToolbar("Cloth Simulation", self.commands)
            self.appendMenu("Cloth Simulation", self.commands)
        def Activated(self): return None
        def Deactivated(self): return None
        def ContextMenu(self, recipient):
            if recipient in ("view", "tree"): self.appendContextMenu("Cloth Simulation", self.commands)
        def GetClassName(self): return "Gui::PythonWorkbench"


    class ClothSewingWorkbench(Gui.Workbench):
        MenuText = "Cloth Sewing"
        ToolTip = "Sewing operations and avatar fitting"
        def Initialize(self):
            import SewingCommands
            import FittingCommands
            self.commands = SewingCommands.COMMANDS + FittingCommands.COMMANDS
            self.appendToolbar("Cloth Sewing", self.commands)
            self.appendMenu("Cloth Sewing", self.commands)
        def Activated(self): return None
        def Deactivated(self): return None
        def ContextMenu(self, recipient):
            if recipient in ("view", "tree"): self.appendContextMenu("Cloth Sewing", self.commands)
        def GetClassName(self): return "Gui::PythonWorkbench"


    Gui.addWorkbench(ClothPatternWorkbench())
    Gui.addWorkbench(ClothSimulationWorkbench())
    Gui.addWorkbench(ClothSewingWorkbench())
else:
    class ClothPatternWorkbench:
        MenuText = "Cloth Pattern"
    class ClothSimulationWorkbench:
        MenuText = "Cloth Simulation"
    class ClothSewingWorkbench:
        MenuText = "Cloth Sewing"
