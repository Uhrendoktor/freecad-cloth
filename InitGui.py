"""FreeCAD GUI registration for the Cloth workbenches."""
from pathlib import Path

_ICON_DIR = Path(__file__).resolve().parent / "resources" / "icons"

try:
    import FreeCADGui as Gui
except ImportError:
    Gui = None

_WorkbenchBase = Gui.Workbench if Gui is not None else object


class _ClothWorkbench(_WorkbenchBase):
    commands = []

    def _register(self, commands):
        self.commands = list(commands)
        self.appendToolbar(self.MenuText, self.commands)
        self.appendMenu(self.MenuText, self.commands)

    def GetResources(self):
        return {"MenuText": self.MenuText, "ToolTip": self.ToolTip, "Icon": self.Icon}

    def Activated(self):
        return None

    def Deactivated(self):
        return None

    def ContextMenu(self, recipient):
        if recipient in ("view", "tree") and self.commands:
            self.appendContextMenu(self.MenuText, self.commands)

    def GetClassName(self):
        return "Gui::PythonWorkbench"


class ClothPatternWorkbench(_ClothWorkbench):
    MenuText = "Cloth Pattern"
    ToolTip = "Parametric sewing-pattern design"
    Icon = "ClothPattern.svg"

    def Initialize(self):
        if self.commands:
            return
        import PatternCommands
        import PatternMarks
        self._register(PatternCommands.COMMANDS + PatternMarks.COMMANDS)


class ClothSimulationWorkbench(_ClothWorkbench):
    MenuText = "Cloth Simulation"
    ToolTip = "3D cloth assembly and simulation"
    Icon = "ClothSimulation.svg"

    def Initialize(self):
        if self.commands:
            return
        import SimulationCommands
        self._register(SimulationCommands.COMMANDS)


class ClothSewingWorkbench(_ClothWorkbench):
    MenuText = "Cloth Sewing"
    ToolTip = "Sewing operations and avatar fitting"
    Icon = "ClothSewing.svg"

    def Initialize(self):
        if self.commands:
            return
        import SewingCommands
        import SewingNetworkCommands
        import FittingCommands
        import AvatarCommands
        self._register(
            SewingCommands.COMMANDS + SewingNetworkCommands.COMMANDS
            + FittingCommands.COMMANDS + AvatarCommands.COMMANDS
        )


if Gui is not None:
    Gui.addIconPath(str(_ICON_DIR))
    Gui.addWorkbench(ClothPatternWorkbench())
    Gui.addWorkbench(ClothSimulationWorkbench())
    Gui.addWorkbench(ClothSewingWorkbench())
