"""Small headless-safe adapter for FreeCAD GUI command registration."""

from pathlib import Path

_ICON_DIR = Path(__file__).resolve().parents[2] / "resources" / "icons"


_ICON_ALIASES = {
    # Reuse generic, context-independent glyphs instead of copying identical SVG files.
    "ClothSewing_Show2D": "ClothPattern_Show2D",
    "ClothDrape_EditTarget": "ClothPattern_EditPiece",
    "ClothFitting_EditAvatar": "ClothPattern_EditPiece",
    "ClothSewing_EditOperation": "ClothPattern_EditPiece",
    "ClothSewingNetwork_EditNetwork": "ClothPattern_EditPiece",
    "ClothSimulation_Edit": "ClothPattern_EditPiece",
    "ClothPattern_CreatePieceTask": "ClothPattern_CreatePiece",
    "ClothSewing_CreateSeam": "ClothPattern_AddSeam",
    "ClothDrape_RefreshTarget": "ClothSimulation_Reset",
    "ClothFitting_CreateSimulation": "ClothSimulation_Create",
    "ClothSewing_CreateMNSewing": "ClothSewingNetwork_CreateNetwork",
    "ClothFitting_SetAvatarMeasurements": "ClothFitting_SetMeasurements",
}


def icon_for_command(command):
    """Return the canonical installed SVG path for a command icon."""
    name = str(command)
    return str(_ICON_DIR / (_ICON_ALIASES.get(name, name) + ".svg"))


class FunctionCommand:
    """Expose a Python callable through FreeCAD's command protocol."""

    def __init__(self, function, tooltip=None, command_name=None):
        self.function = function
        self.tooltip = tooltip
        self.command_name = command_name or function.__name__

    def Activated(self):
        """Provide the public Activated operation."""
        return self.function()

    def GetResources(self):
        """Provide the public GetResources operation."""
        return {
            "MenuText": self.function.__name__.replace("_", " ").title(),
            "ToolTip": self.tooltip or self.function.__doc__ or "Cloth command",
            "Pixmap": icon_for_command(self.command_name),
        }


def register_commands(gui, commands):
    """Register ``name -> callable`` pairs with FreeCAD's command protocol."""
    if not hasattr(gui, "addCommand"):
        return
    for name, function in commands.items():
        gui.addCommand(name, FunctionCommand(function, command_name=name))
