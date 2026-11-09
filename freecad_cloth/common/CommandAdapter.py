# Copyright (C) 2026 FreeCAD Cloth contributors
"""Small headless-safe adapter for FreeCAD GUI command registration."""

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Protocol, TypeAlias

CommandCallable: TypeAlias = Callable[[], object]


class GuiCommandRegistrar(Protocol):
    """Minimal FreeCAD GUI command-registration interface."""

    def addCommand(self, name: str, command: "FunctionCommand") -> None:
        """Register one command instance under its stable GUI identifier.

        Args:
            name: Command identifier used by FreeCAD's menus and toolbars.
            command: Handler object implementing the FreeCAD command protocol.
        """
        ...


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
    """Resolve a command identifier to its canonical installed SVG icon.

    Args:
        command: Stable FreeCAD command identifier.

    Returns:
        Absolute path of the matching SVG resource.
    """
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
        """Create an adapter for one command callback.

        Args:
            function: Callable invoked when the user activates the command.
            tooltip: Optional help text shown by FreeCAD.
            command_name: Stable command identifier used to locate its icon.
        """
        self.function = function
        self.tooltip = tooltip
        self.command_name = command_name or getattr(function, "__name__", "command")

    def Activated(self) -> object:
        """Invoke the wrapped command handler.

        Returns:
            Result returned by the command handler.
        """
        return self.function()

    def GetResources(self) -> dict[str, str]:
        """Build the menu, tooltip, and icon resources for FreeCAD.

        Returns:
            FreeCAD command resource strings keyed by their protocol names.
        """
        return {
            "MenuText": str(getattr(self.function, "__name__", "command"))
            .replace("_", " ")
            .title(),
            "ToolTip": self.tooltip or getattr(self.function, "__doc__", None) or "Cloth command",
            "Pixmap": icon_for_command(self.command_name),
        }


def register_commands(
    gui: GuiCommandRegistrar,
    commands: Mapping[str, CommandCallable],
) -> None:
    """Register named callables with FreeCAD's command protocol.

    Args:
        gui: FreeCAD GUI object that implements the command-registration protocol.
        commands: Mapping from stable command identifiers to their callable handlers.
    """
    if not hasattr(gui, "addCommand"):
        return
    for name, function in commands.items():
        gui.addCommand(name, FunctionCommand(function, command_name=name))
