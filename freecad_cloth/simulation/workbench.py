"""Simulation workbench registration facade.

Command implementations remain in the package tree; this module owns the
FreeCAD workbench boundary and resolves its icon to the installed root resource.
"""

from collections.abc import Callable
from pathlib import Path
from types import ModuleType

from freecad_cloth.gui import ClothWorkbenchBase

AVATAR_ENTRY_COMMANDS = (
    "ClothFitting_CreateAvatar",
    "ClothFitting_EditAvatar",
    "ClothFitting_PoseAvatar",
)


class ClothSimulationWorkbench(ClothWorkbenchBase):
    MenuText = "Cloth Simulation"
    ToolTip = "3D cloth assembly and simulation"

    def __init__(
        self,
        *,
        gui: ModuleType | None = None,
        toolbar_sink: Callable[..., object] | None = None,
        menu_sink: Callable[..., object] | None = None,
    ):
        super().__init__(gui=gui, toolbar_sink=toolbar_sink, menu_sink=menu_sink)
        self.Icon = str(
            Path(__file__).resolve().parents[2] / "resources" / "icons" / "ClothSimulation.svg"
        )

    def Activated(self):
        import FreeCAD as App

        import freecad_cloth.simulation.DrapeCommands as DrapeCommands
        from freecad_cloth.sewing.SeamOverlay import activate_seam_overlay
        from freecad_cloth.sewing.SewingView import apply_seam_colors

        DrapeCommands.register_gui_commands()
        if App.ActiveDocument is not None:
            apply_seam_colors(App.ActiveDocument.Objects)
            activate_seam_overlay(App.ActiveDocument)

    def Initialize(
        self,
        *,
        drape_commands: ModuleType | None = None,
        simulation_commands: ModuleType | None = None,
        register_fn: Callable[..., object] | None = None,
    ):
        if self.commands:
            return
        if drape_commands is None:
            import freecad_cloth.simulation.DrapeCommands as drape_commands
        if simulation_commands is None:
            import freecad_cloth.simulation.SimulationCommands as simulation_commands

        drape_commands.register_gui_commands()
        register_groups = self.register if register_fn is None else register_fn
        register_groups(
            (
                ("Avatar & Fitting", AVATAR_ENTRY_COMMANDS),
                (
                    "Simulation",
                    simulation_commands.COMMANDS
                    + ["ClothRealtimePreview"]
                    + drape_commands.COMMANDS,
                ),
            )
        )
