"""Small headless-safe adapter for FreeCAD GUI command registration."""
from pathlib import Path


_ICON_DIR = Path(__file__).resolve().parents[2] / "resources" / "icons"


def icon_for_command(command):
    """Return the installed SVG path for a command icon."""
    return str(_ICON_DIR / (str(command) + ".svg"))


class FunctionCommand:
    """Expose a Python callable through FreeCAD's command protocol."""

    def __init__(self, function, tooltip=None, command_name=None):
        self.function = function
        self.tooltip = tooltip
        self.command_name = command_name or function.__name__

    def Activated(self):
        return self.function()

    def GetResources(self):
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
