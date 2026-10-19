# Copyright (C) 2026 FreeCAD Cloth contributors
"""Shared FreeCAD startup for the classic and namespaced loaders."""

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

    avatar_module = import_module("freecad_cloth.avatar")
    pattern_module = import_module("freecad_cloth.pattern.workbench")
    sewing_module = import_module("freecad_cloth.sewing.workbench")
    simulation_module = import_module("freecad_cloth.simulation.workbench")

    if not set(simulation_module.AVATAR_ENTRY_COMMANDS).issubset(
        avatar_module.AvatarCommands.COMMANDS
    ):
        msg = "Cloth Simulation avatar menu references unregistered commands"
        raise RuntimeError(msg)

    workbenches = (
        ("ClothPatternWorkbench", pattern_module.ClothPatternWorkbench),
        ("ClothSimulationWorkbench", simulation_module.ClothSimulationWorkbench),
        ("ClothSewingWorkbench", sewing_module.ClothSewingWorkbench),
    )
    registered = set(gui.listWorkbenches())
    for workbench_name, workbench_type in workbenches:
        if workbench_name not in registered:
            gui.addWorkbench(workbench_type())
            registered.add(workbench_name)
