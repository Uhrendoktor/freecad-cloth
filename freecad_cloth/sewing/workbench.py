"""Sewing workbench registration facade."""
from freecad_cloth.gui import ClothWorkbenchBase


COMMAND_GROUPS = (
    ("Sewing Creation", ("ClothSewing_CreateSeam", "ClothSewing_CreateMNSewing", "ClothSewing_CreateNetwork", "ClothSewing_FreeSewing")),
    ("Sewing Editing", ("ClothSewing_CreateOperation", "ClothSewing_EditOperation", "ClothSewing_EditNetwork", "ClothSewing_ReverseSeam", "ClothSewing_ToggleAlignment")),
    ("Validation & View", ("ClothSewing_Validate", "ClothSewing_RepairSeam", "ClothSewing_Show2D")),
)
TOOLBAR_COMMANDS = ("ClothSewing_CreateSeam", "ClothSewing_CreateOperation", "ClothSewing_Validate")


class ClothSewingWorkbench(ClothWorkbenchBase):
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
        groups = list(COMMAND_GROUPS)
        groups.append(("Fitting & Avatar", FittingCommands.COMMANDS + AvatarCommands.COMMANDS))
        expected = SewingCommands.COMMANDS + SewingNetworkCommands.COMMANDS + FittingCommands.COMMANDS + AvatarCommands.COMMANDS
        grouped = [c for _, commands in groups for c in self.normalize_commands(commands)]
        if len(grouped) != len(set(grouped)) or set(grouped) != set(expected):
            raise ValueError("Sewing workbench command groups are out of sync")
        self.register(groups, toolbar_name=self.MenuText, toolbar_commands=TOOLBAR_COMMANDS)
