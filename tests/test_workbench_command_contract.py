# Copyright (C) 2026 FreeCAD Cloth contributors
"""Headless/static contract checks for package-owned workbench registration."""

import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_WORKBENCHES = {
    "freecad_cloth.pattern.workbench": (
        "ClothPatternWorkbench",
        "Cloth Pattern",
        ("freecad_cloth.pattern.PatternCommands", "freecad_cloth.pattern.PatternMarks"),
    ),
    "freecad_cloth.simulation.workbench": (
        "ClothSimulationWorkbench",
        "Cloth Simulation",
        ("freecad_cloth.simulation.SimulationCommands", "freecad_cloth.simulation.DrapeCommands"),
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


def _check(condition: object, message: str) -> None:
    """Raise a descriptive test failure when a required condition is false.

    Args:
        condition: Observed predicate that must hold for the contract.
        message: Explanation identifying the violated registration condition.

    Raises:
        AssertionError: If the supplied predicate is false.
    """
    if not condition:
        raise AssertionError(message)


def test_workbench_modules_are_package_owned_and_importable() -> None:
    """Verify each package-owned workbench imports with valid resources and command modules."""
    for module_name, (class_name, menu, modules) in _WORKBENCHES.items():
        module = importlib.import_module(module_name)
        workbench = getattr(module, class_name)()
        _check(workbench.MenuText == menu, f"{module_name} menu title must match its contract")
        _check(
            workbench.GetClassName() == "Gui::PythonWorkbench",
            f"{module_name} must expose the FreeCAD workbench class",
        )
        _check(Path(workbench.Icon).is_file(), f"{module_name} icon path must exist")
        _check(workbench.commands == [], f"{module_name} commands must start empty")
        for command_module in modules:
            _check(
                bool(importlib.import_module(command_module).COMMANDS),
                f"{command_module} must expose command identifiers",
            )


def test_command_ids_exist_and_are_unique() -> None:
    """Verify all workbench commands are unique both within and across modules."""
    seen: set[str] = set()
    for contract in _WORKBENCHES.values():
        for module_name in contract[2]:
            commands = tuple(importlib.import_module(module_name).COMMANDS)
            _check(
                len(commands) == len(set(commands)),
                f"{module_name} must not repeat command identifiers",
            )
            _check(
                not seen.intersection(commands),
                f"{module_name} command identifiers must not overlap prior modules",
            )
            seen.update(commands)


def test_init_gui_is_bootstrap_only() -> None:
    """Verify the root GUI loader delegates registration and imports no legacy modules."""
    source = (ROOT / "InitGui.py").read_text(encoding="utf-8")
    _check(
        "from freecad_cloth.bootstrap import initialize_workbenches" in source,
        "root GUI loader must import the shared bootstrap",
    )
    _check(
        "initialize_workbenches(Path(__file__).resolve().parent)" in source,
        "root GUI loader must initialize with its package directory",
    )
    _check("Gui.addWorkbench(" not in source, "root GUI loader must not duplicate registration")
    for legacy in (
        "import PatternCommands",
        "import SewingNetworkCommands",
        "import SewingNetworkGui",
        "import DrapeTarget",
    ):
        _check(legacy not in source, f"root GUI loader must not import {legacy!r}")


def test_all_implementation_python_files_are_inside_package_tree() -> None:
    """Verify implementation modules remain inside the package-owned source tree."""
    forbidden = {
        "PatternCommands.py",
        "SewingNetworkCommands.py",
        "SewingNetworkGui.py",
        "FittingCommands.py",
    }
    root_python = {path.name for path in ROOT.glob("*.py")}
    _check(
        root_python <= {"Init.py", "InitGui.py", "sitecustomize.py"},
        "root Python files must remain limited to the three supported entrypoints",
    )
    _check(
        not root_python.intersection(forbidden),
        "legacy implementation modules must not reappear at the repository root",
    )
