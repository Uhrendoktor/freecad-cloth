"""Sewing workbench registration facade."""
from freecad_cloth.gui import ClothWorkbenchBase


COMMAND_GROUPS = (
    ("Sewing Creation", ("ClothSewing_CreateSeam", "ClothSewing_CreateMNSewing", "ClothSewing_CreateNetwork", "ClothSewing_FreeSewing")),
    ("Sewing Editing", ("ClothSewing_CreateOperation", "ClothSewing_EditOperation", "ClothSewing_EditNetwork", "ClothSewing_ReverseSeam", "ClothSewing_ToggleAlignment")),
    ("Validation & View", ("ClothSewing_Validate", "ClothSewing_RepairSeam", "ClothSewing_Show2D")),
)
TOOLBAR_COMMANDS = ("ClothSewing_CreateSeam", "ClothSewing_CreateOperation", "ClothSewing_Validate")


def _validate_sewing_command_groups(groups, expected):
    grouped = []
    expected = ClothWorkbenchBase.normalize_commands(expected)
    for _group_name, commands in groups:
        grouped.extend(ClothWorkbenchBase.normalize_commands(commands))
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


class ClothSewingWorkbench(ClothWorkbenchBase):
    MenuText = "Cloth Sewing"
    ToolTip = "Sewing operations and avatar fitting"
    Icon = "ClothSewing.svg"

    def Initialize(self):
        if self.commands:
            return
        import freecad_cloth.sewing.SewingCommands
        import freecad_cloth.sewing.SewingNetworkCommands
        import freecad_cloth.simulation.FittingCommands
        import freecad_cloth.avatar.AvatarCommands
        groups = list(COMMAND_GROUPS)
        groups.append(("Fitting & Avatar", FittingCommands.COMMANDS + AvatarCommands.COMMANDS))
        expected = SewingCommands.COMMANDS + SewingNetworkCommands.COMMANDS + FittingCommands.COMMANDS + AvatarCommands.COMMANDS
        _validate_sewing_command_groups(groups, expected)
        self.register(groups, toolbar_name=self.MenuText, toolbar_commands=TOOLBAR_COMMANDS)
