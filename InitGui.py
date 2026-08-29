"""FreeCAD GUI registration for the Cloth workbenches.

The module is intentionally import-safe outside FreeCAD.  Workbench command
modules are imported lazily from ``Initialize`` so a headless Python process
can inspect/package the repository without importing FreeCAD or Qt.
"""
from pathlib import Path


_ICON_DIR = Path(__file__).resolve().parent / "resources" / "icons"


def _icon(name):
    """Return an absolute icon path suitable for FreeCAD's workbench API."""
    return str(_ICON_DIR / name)


try:
    import FreeCADGui as Gui
except ImportError:
    Gui = None

_WorkbenchBase = Gui.Workbench if Gui is not None else object


class ClothPatternWorkbench(_WorkbenchBase):
    MenuText = "Cloth Pattern"
    ToolTip = "Parametric sewing-pattern design"
    Icon = _icon("ClothPattern.svg")
    commands = ()

    def Initialize(self):
        if self.commands:
            return
        import PatternCommands
        import PatternMarks
        self.commands = tuple(PatternCommands.COMMANDS + PatternMarks.COMMANDS)
        self.appendToolbar(self.MenuText, self.commands)
        self.appendMenu(self.MenuText, self.commands)

    def Activated(self): return None
    def Deactivated(self): return None

    def ContextMenu(self, recipient):
        if recipient in ("view", "tree") and self.commands:
            self.appendContextMenu(self.MenuText, self.commands)

    def GetClassName(self): return "Gui::PythonWorkbench"


class ClothSimulationWorkbench(_WorkbenchBase):
    MenuText = "Cloth Simulation"
    ToolTip = "3D cloth assembly and simulation"
    Icon = _icon("ClothSimulation.svg")
    commands = ()

    def Initialize(self):
        if self.commands:
            return
        import SimulationCommands
        self.commands = tuple(SimulationCommands.COMMANDS)
        self.appendToolbar(self.MenuText, self.commands)
        self.appendMenu(self.MenuText, self.commands)

    def Activated(self): return None
    def Deactivated(self): return None

    def ContextMenu(self, recipient):
        if recipient in ("view", "tree") and self.commands:
            self.appendContextMenu(self.MenuText, self.commands)

    def GetClassName(self): return "Gui::PythonWorkbench"


class ClothSewingWorkbench(_WorkbenchBase):
    MenuText = "Cloth Sewing"
    ToolTip = "Sewing operations and avatar fitting"
    Icon = _icon("ClothSewing.svg")
    commands = ()

    def Initialize(self):
        if self.commands:
            return
        import SewingCommands
        import FittingCommands
        self.commands = tuple(SewingCommands.COMMANDS + FittingCommands.COMMANDS)
        self.appendToolbar(self.MenuText, self.commands)
        self.appendMenu(self.MenuText, self.commands)

    def Activated(self): return None
    def Deactivated(self): return None

    def ContextMenu(self, recipient):
        if recipient in ("view", "tree") and self.commands:
            self.appendContextMenu(self.MenuText, self.commands)

    def GetClassName(self): return "Gui::PythonWorkbench"


if Gui is not None:
    Gui.addWorkbench(ClothPatternWorkbench())
    Gui.addWorkbench(ClothSimulationWorkbench())
    Gui.addWorkbench(ClothSewingWorkbench())
