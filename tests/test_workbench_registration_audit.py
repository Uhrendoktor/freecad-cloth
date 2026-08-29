"""Focused regression checks for native Cloth workbench registration.

The existing contract test checks the primary command groups. This audit adds
coverage for the M:N/free-sewing command group, which is explicitly registered
by the Sewing workbench and therefore must not be omitted from its registration
expression.
"""
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _class(tree, name):
    return next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == name
    )


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


def _register_expression(initialize):
    for node in ast.walk(initialize):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "_register":
            continue
        assert len(node.args) == 1
        return node.args[0]
    raise AssertionError("workbench Initialize() must call _register once")


def test_sewing_workbench_registers_free_sewing_command_group():
    tree = ast.parse((ROOT / "InitGui.py").read_text(encoding="utf-8"))
    sewing = _class(tree, "ClothSewingWorkbench")
    initialize = next(
        node for node in sewing.body
        if isinstance(node, ast.FunctionDef) and node.name == "Initialize"
    )

    expression = _register_expression(initialize)
    modules = {
        node.value.id
        for node in ast.walk(expression)
        if isinstance(node, ast.Attribute)
        and node.attr == "COMMANDS"
        and isinstance(node.value, ast.Name)
    }
    assert modules == {"SewingCommands", "SewingNetworkCommands", "FittingCommands"}

    # Keep the assertion tied to the actual module contents so adding a new
    # network command cannot silently leave it outside the native workbench.
    assert _literal_commands("SewingNetworkCommands")


def test_workbench_command_groups_do_not_overlap():
    groups = {
        "Pattern": _literal_commands("PatternCommands") | _literal_commands("PatternMarks"),
        "Sewing": (
            _literal_commands("SewingCommands")
            | _literal_commands("SewingNetworkCommands")
            | _literal_commands("FittingCommands")
        ),
        "Simulation": _literal_commands("SimulationCommands"),
    }

    names = {}
    for workbench, commands in groups.items():
        assert commands, f"{workbench} workbench has no commands"
        for command in commands:
            previous = names.setdefault(command, workbench)
            assert previous == workbench, (
                f"command {command!r} is registered by both "
                f"{previous} and {workbench}"
            )
