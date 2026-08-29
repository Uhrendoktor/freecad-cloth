"""Headless contract checks for the three registered Cloth workbenches.

This deliberately avoids FreeCAD/Qt: the implementation must remain import-safe
while command modules are loaded lazily by each workbench's ``Initialize``.
"""
from __future__ import annotations

import ast
import importlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

EXPECTED = {
    "ClothPatternWorkbench": {
        "menu": "Cloth Pattern",
        "commands": {
            "ClothPattern_CreatePieceTask",
            "ClothPattern_EditPiece",
            "ClothPattern_Show2D",
        },
        "modules": ("PatternCommands", "PatternMarks"),
    },
    "ClothSewingWorkbench": {
        "menu": "Cloth Sewing",
        "commands": {
            "ClothSewing_CreateSeam",
            "ClothSewing_CreateOperation",
            "ClothSewing_EditOperation",
            "ClothSewing_ReverseSeam",
            "ClothSewing_ToggleAlignment",
            "ClothSewing_Validate",
            "ClothSewing_Show2D",
        },
        "modules": ("SewingCommands", "FittingCommands"),
    },
    "ClothSimulationWorkbench": {
        "menu": "Cloth Simulation",
        "commands": {
            "ClothSimulation_Create",
            "ClothSimulation_CreateDrape",
            "ClothSimulation_Edit",
            "ClothSimulation_Step",
        },
        "modules": ("SimulationCommands",),
    },
}


def _literal_commands(module_name):
    tree = ast.parse((ROOT / f"{module_name}.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "COMMANDS"
            for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            assert isinstance(value, list), f"{module_name}.COMMANDS must be a list"
            return set(value)
    raise AssertionError(f"{module_name}.COMMANDS is missing")


def test_registered_workbenches_and_command_groups():
    gui_source = (ROOT / "InitGui.py").read_text(encoding="utf-8")
    tree = ast.parse(gui_source)

    classes = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
    }
    assert set(EXPECTED) <= classes

    for class_name, spec in EXPECTED.items():
        node = classes[class_name]
        attributes = {
            statement.targets[0].id: statement.value
            for statement in node.body
            if isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
        }
        assert ast.literal_eval(attributes["MenuText"]) == spec["menu"]

        # The workbench starts with an empty command tuple and imports command
        # modules only from Initialize. This keeps package inspection headless.
        commands = attributes["commands"]
        assert isinstance(commands, ast.Tuple) and not commands.elts
        initialize = next(
            node2 for node2 in node.body
            if isinstance(node2, ast.FunctionDef) and node2.name == "Initialize"
        )
        imported = {
            alias.name
            for node2 in ast.walk(initialize)
            if isinstance(node2, ast.Import)
            for alias in node2.names
        }
        assert imported == set(spec["modules"])

        command_names = set()
        for module in spec["modules"]:
            command_names |= _literal_commands(module)
        assert spec["commands"] <= command_names


def test_command_modules_are_import_safe_without_freecad():
    for module_name in (
        "PatternCommands",
        "PatternMarks",
        "SewingCommands",
        "FittingCommands",
        "SimulationCommands",
    ):
        module = importlib.import_module(module_name)
        assert hasattr(module, "COMMANDS"), f"{module_name} must expose COMMANDS"


print("Workbench command contract checks passed")
