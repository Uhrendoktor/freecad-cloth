# Copyright (C) 2026 FreeCAD Cloth contributors
"""Headless/static contract checks for package-owned workbench registration."""

import importlib
from pathlib import Path

from support.assertions import require

ROOT: Path = Path(__file__).resolve().parents[1]
_WORKBENCHES: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "freecad_cloth.pattern.workbench": (
        "ClothPatternWorkbench",
        "Cloth Pattern",
        ("freecad_cloth.pattern.PatternCommands", "freecad_cloth.pattern.PatternMarks"),
    ),
    "freecad_cloth.simulation.workbench": (
        "ClothSimulationWorkbench",
        "Cloth Simulation",
        (
            "freecad_cloth.simulation.SimulationCommands",
            "freecad_cloth.simulation.DrapeCommands",
        ),
    ),
    "freecad_cloth.sewing.workbench": (
        "ClothSewingWorkbench",
        "Cloth Sewing",
        (
            "freecad_cloth.sewing.SewingCommands",
            "freecad_cloth.sewing.SewingNetworkCommands",
            "freecad_cloth.avatar.FittingCommands",
            "freecad_cloth.avatar.AvatarCommands",
        ),
    ),
}


def test_workbench_modules_are_package_owned_and_importable() -> None:
    """Verify declared workbench modules and command providers are importable."""
    for module_name, (class_name, menu, modules) in _WORKBENCHES.items():
        module = importlib.import_module(module_name)
        workbench = getattr(module, class_name)()
        require(
            condition=workbench.MenuText == menu,
            message=f"{module_name} must expose the expected menu label {menu!r}",
        )
        require(
            condition=workbench.GetClassName() == "Gui::PythonWorkbench",
            message=f"{module_name} must identify itself as a Python workbench",
        )
        require(
            condition=Path(workbench.Icon).is_file(),
            message=f"{module_name} must reference an existing icon file",
        )
        require(
            condition=workbench.commands == [],
            message=f"{module_name} must defer command registration until initialization",
        )
        for command_module in modules:
            provider = importlib.import_module(command_module)
            require(
                condition=bool(provider.COMMANDS),
                message=f"{command_module} must expose at least one command",
            )


def test_command_ids_exist_and_are_unique() -> None:
    """Verify command identifiers are unique within and across workbenches."""
    seen: set[str] = set()
    for contract in _WORKBENCHES.values():
        for module_name in contract[2]:
            commands = tuple(importlib.import_module(module_name).COMMANDS)
            require(
                condition=len(commands) == len(set(commands)),
                message=f"{module_name} must not repeat a command identifier",
            )
            require(
                condition=not seen.intersection(commands),
                message=f"{module_name} command identifiers must not overlap prior modules",
            )
            seen.update(commands)


def test_command_handlers_match_declared_command_ids() -> None:
    """Require every declared avatar/fitting command to have one dispatch handler."""
    for module_name, handler_name in (
        ("freecad_cloth.avatar.AvatarCommands", "_HANDLERS"),
        ("freecad_cloth.avatar.FittingCommands", "_COMMAND_HANDLERS"),
    ):
        module = importlib.import_module(module_name)
        handlers = getattr(module, handler_name)
        commands = set(module.COMMANDS)
        require(
            condition=commands == set(handlers),
            message=f"{module_name} command IDs must match their dispatch handlers exactly",
        )


def test_init_gui_is_bootstrap_only() -> None:
    """Verify the legacy GUI entry point delegates registration to the bootstrap."""
    source = (ROOT / "InitGui.py").read_text(encoding="utf-8")
    require(
        condition="from freecad_cloth.bootstrap import initialize_workbenches" in source,
        message="InitGui.py must import the canonical workbench bootstrap",
    )
    require(
        condition="initialize_workbenches(Path(__file__).resolve().parent)" in source,
        message="InitGui.py must delegate registration with its installation root",
    )
    require(
        condition="Gui.addWorkbench(" not in source,
        message="InitGui.py must not duplicate workbench registration",
    )
    for legacy in (
        "import PatternCommands",
        "import SewingNetworkCommands",
        "import SewingNetworkGui",
        "import DrapeTarget",
    ):
        require(
            condition=legacy not in source,
            message=f"InitGui.py must not import legacy module {legacy!r}",
        )


def test_all_implementation_python_files_are_inside_package_tree() -> None:
    """Keep implementation modules inside the package instead of at repository root."""
    forbidden = {
        "PatternCommands.py",
        "SewingNetworkCommands.py",
        "SewingNetworkGui.py",
        "FittingCommands.py",
    }
    root_python = {path.name for path in ROOT.glob("*.py")}
    allowed_root_python = {"Init.py", "InitGui.py", "sitecustomize.py"}
    require(
        condition=root_python <= allowed_root_python,
        message="Only FreeCAD loader entrypoints may remain at the repository root",
    )
    require(
        condition=not root_python.intersection(forbidden),
        message="Legacy workbench implementation modules must stay inside package directories",
    )
