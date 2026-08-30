"""FreeCAD GUI registration for the Cloth workbenches.

The three workbenches deliberately share only registration mechanics. Pattern,
Sewing, and Simulation remain separate UI entry points while their document
objects form one dependency pipeline.
"""
from pathlib import Path

_ICON_DIR = Path(__file__).resolve().parent / "resources" / "icons"

try:
    import FreeCADGui as Gui
except ImportError:
    Gui = None

_WorkbenchBase = Gui.Workbench if Gui is not None else object


class _ClothWorkbench(_WorkbenchBase):
    """Small common registration shell for the Cloth workbenches.

    ``commands`` is instance-owned: FreeCAD can instantiate workbench classes
    more than once during tests or reloads, and command state must never leak
    from one workbench instance into another.
    """

    def __init__(self):
        if Gui is not None:
            super().__init__()
        self.commands = []

    @staticmethod
    def _normalize_commands(commands):
        registered = []
        for command in commands:
            command = str(command)
            if command and command not in registered:
                registered.append(command)
        return registered

    def _register(self, commands):
        """Register an immutable command set exactly once per instance."""
        self._register_groups(((self.MenuText, commands),))

    def _register_groups(self, groups, toolbar_name=None):
        """Register deterministic menu groups exactly once.

        A command may belong to only one group. The same normalized command
        list is retained on ``self.commands`` for context-menu registration.
        ``toolbar_name`` keeps a stable single toolbar while the menu exposes
        the workflow groups as nested sections.
        """
        if self.commands:
            return
        normalized_groups = []
        registered = []
        for group_name, commands in groups:
            group_name = str(group_name)
            group_commands = self._normalize_commands(commands)
            duplicates = [command for command in group_commands if command in registered]
            if duplicates:
                raise ValueError("commands registered in multiple workbench groups: %s" % ", ".join(duplicates))
            if not group_name or not group_commands:
                continue
            normalized_groups.append((group_name, group_commands))
            registered.extend(group_commands)
        self.commands = registered
        if Gui is not None:
            if toolbar_name:
                self.appendToolbar(toolbar_name, registered)
            else:
                for group_name, group_commands in normalized_groups:
                    self.appendToolbar(group_name, group_commands)
            for group_name, group_commands in normalized_groups:
                self.appendMenu([self.MenuText, group_name], group_commands)

    def GetResources(self):
        """Return the standard FreeCAD workbench metadata contract."""
        return {
            "MenuText": self.MenuText,
            "ToolTip": self.ToolTip,
            "Icon": self.Icon,
        }

    def Activated(self):
        return None

    def Deactivated(self):
        return None

    def ContextMenu(self, recipient):
        if recipient in ("view", "tree") and self.commands:
            self.appendContextMenu(self.MenuText, self.commands)

    def GetClassName(self):
        """Return FreeCAD's Python-workbench class identifier."""
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
        import DrapeCommands
        self._register(SimulationCommands.COMMANDS + DrapeCommands.COMMANDS)


SEWING_COMMAND_GROUPS = (
    (
        "Sewing Creation",
        (
            "ClothSewing_CreateSeam",
            "ClothSewing_CreateMNSewing",
            "ClothSewing_CreateNetwork",
            "ClothSewing_FreeSewing",
        ),
    ),
    (
        "Sewing Editing",
        (
            "ClothSewing_CreateOperation",
            "ClothSewing_EditOperation",
            "ClothSewing_EditNetwork",
            "ClothSewing_ReverseSeam",
            "ClothSewing_ToggleAlignment",
        ),
    ),
    (
        "Validation & View",
        (
            "ClothSewing_Validate",
            "ClothSewing_RepairSeam",
            "ClothSewing_Show2D",
        ),
    ),
)


def _validate_sewing_command_groups(groups, expected):
    """Fail closed before any toolbar/menu group is handed to FreeCAD."""
    grouped = []
    for _group_name, commands in groups:
        grouped.extend(_ClothWorkbench._normalize_commands(commands))
    expected = _ClothWorkbench._normalize_commands(expected)
    if len(grouped) != len(set(grouped)):
        raise ValueError("Sewing workbench command groups contain duplicates")
    if set(grouped) != set(expected):
        missing = sorted(set(expected) - set(grouped))
        extra = sorted(set(grouped) - set(expected))
        detail = []
        if missing:
            detail.append("missing: %s" % ", ".join(missing))
        if extra:
            detail.append("unexpected: %s" % ", ".join(extra))
        raise ValueError("Sewing workbench command groups are out of sync (%s)" % "; ".join(detail))


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
        groups = list(SEWING_COMMAND_GROUPS)
        groups.append(("Fitting & Avatar", FittingCommands.COMMANDS + AvatarCommands.COMMANDS))
        expected = SewingCommands.COMMANDS + SewingNetworkCommands.COMMANDS
        expected += FittingCommands.COMMANDS + AvatarCommands.COMMANDS
        _validate_sewing_command_groups(groups, expected)
        self._register_groups(groups, toolbar_name=self.MenuText)


if Gui is not None:
    Gui.addIconPath(str(_ICON_DIR))
    Gui.addWorkbench(ClothPatternWorkbench())
    Gui.addWorkbench(ClothSimulationWorkbench())
    Gui.addWorkbench(ClothSewingWorkbench())
