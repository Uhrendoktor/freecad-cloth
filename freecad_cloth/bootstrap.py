# Copyright (C) 2026 FreeCAD Cloth contributors
"""Shared FreeCAD startup for the classic and namespaced loaders."""

from pathlib import Path


def initialize_workbenches(installation_root: Path) -> None:
    """Register Cloth workbenches and resolve resources relative to the installation.

    Args:
        installation_root: Root directory containing the installed workbench resources.

    Raises:
        RuntimeError: If a simulation menu references an unregistered avatar command.
    """
    try:
        import FreeCADGui as Gui
    except ImportError:
        return

    icon_dir = Path(installation_root).resolve() / "resources" / "icons"
    if icon_dir.is_dir():
        Gui.addIconPath(str(icon_dir))

    from freecad_cloth.avatar import AvatarCommands
    from freecad_cloth.pattern.workbench import ClothPatternWorkbench
    from freecad_cloth.sewing.workbench import ClothSewingWorkbench
    from freecad_cloth.simulation.workbench import (
        AVATAR_ENTRY_COMMANDS,
        ClothSimulationWorkbench,
    )

    if not set(AVATAR_ENTRY_COMMANDS).issubset(AvatarCommands.COMMANDS):
        raise RuntimeError("Cloth Simulation avatar menu references unregistered commands")

    workbenches = (
        ("ClothPatternWorkbench", ClothPatternWorkbench),
        ("ClothSimulationWorkbench", ClothSimulationWorkbench),
        ("ClothSewingWorkbench", ClothSewingWorkbench),
    )
    registered = set(Gui.listWorkbenches())
    for workbench_name, workbench_type in workbenches:
        if workbench_name not in registered:
            Gui.addWorkbench(workbench_type())
            registered.add(workbench_name)
