"""Small headless-safe adapter for FreeCAD GUI command registration."""

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Protocol, TypeAlias

CommandCallable: TypeAlias = Callable[[], object]


class GuiCommandRegistrar(Protocol):
    """Minimal FreeCAD GUI command-registration interface."""

    def addCommand(self, name: str, command: "FunctionCommand") -> None: ...


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


def icon_for_command(command: str) -> str:
    """Return the canonical installed SVG path for a command icon."""
    name = str(command)
    return str(_ICON_DIR / (_ICON_ALIASES.get(name, name) + ".svg"))


class FunctionCommand:
    """Expose a Python callable through FreeCAD's command protocol."""

    def __init__(
        self,
        function: CommandCallable,
        tooltip: str | None = None,
        command_name: str | None = None,
    ) -> None:
        self.function = function
        self.tooltip = tooltip
        self.command_name = command_name or getattr(function, "__name__", "command")

    def Activated(self) -> object:
        """Provide the public Activated operation."""
        return self.function()

    def GetResources(self) -> dict[str, str]:
        """Provide the public GetResources operation."""
        return {
            "MenuText": self.function.__name__.replace("_", " ").title(),
            "ToolTip": self.tooltip or getattr(self.function, "__doc__", None) or "Cloth command",
            "Pixmap": icon_for_command(self.command_name),
        }


def register_commands(
    gui: GuiCommandRegistrar,
    commands: Mapping[str, CommandCallable],
) -> None:
    """Register ``name -> callable`` pairs with FreeCAD's command protocol."""
    if not hasattr(gui, "addCommand"):
        return
    for name, function in commands.items():
        gui.addCommand(name, FunctionCommand(function, command_name=name))
