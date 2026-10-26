# Copyright (C) 2026 FreeCAD Cloth contributors
"""Shared FreeCAD startup for the classic and namespaced loaders."""

from importlib import import_module
from importlib import import_module
from pathlib import Path


def initialize_workbenches(installation_root: Path) -> None:
    """Register Cloth workbenches and resolve resources relative to the installation.

    Args:
        installation_root: Root directory containing the installed workbench resources.

    Raises:
        RuntimeError: If a simulation menu references an unregistered avatar command.
    """
    try:
        gui = import_module("FreeCADGui")
    except ImportError:
        return

    icon_dir = Path(installation_root).resolve() / "resources" / "icons"
    if icon_dir.is_dir():
        gui.addIconPath(str(icon_dir))

    avatar_commands = import_module("freecad_cloth.avatar.AvatarCommands")
    pattern_workbench = import_module("freecad_cloth.pattern.workbench")
    sewing_workbench = import_module("freecad_cloth.sewing.workbench")
    fitting_handoff = import_module("freecad_cloth.simulation.FittingHandoff")
    simulation_workbench = import_module("freecad_cloth.simulation.workbench")

    fitting_handoff.register_fitting_handoff_commands(gui)

    command_ids = import_module("freecad_cloth.shared.CommandIds")

    if not set(command_ids.AVATAR_ENTRY_COMMANDS).issubset(avatar_commands.COMMANDS):
        msg = "Cloth Simulation avatar menu references unregistered commands"
        raise RuntimeError(msg)

    workbenches = (
        ("ClothPatternWorkbench", pattern_workbench.ClothPatternWorkbench),
        ("ClothSimulationWorkbench", simulation_workbench.ClothSimulationWorkbench),
        ("ClothSewingWorkbench", sewing_workbench.ClothSewingWorkbench),
    )
    registered = set(gui.listWorkbenches())
    for workbench_name, workbench_type in workbenches:
        if workbench_name not in registered:
            gui.addWorkbench(workbench_type())
            registered.add(workbench_name)
