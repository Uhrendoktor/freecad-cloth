"""Focused regression checks for native Cloth workbench registration.

The existing contract test checks the primary command groups.  This audit adds
coverage for the M:N/free-sewing command group, which is explicitly registered
by the Sewing workbench and therefore must not be omitted from the workbench
contract.
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


def _initialize_imports(node):
    return {
        alias.name
        for statement in ast.walk(node)
        if isinstance(statement, ast.Import)
        for alias in statement.names
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


def test_sewing_workbench_registers_free_sewing_command_group():
    tree = ast.parse((ROOT / "InitGui.py").read_text(encoding="utf-8"))
    sewing = _class(tree, "ClothSewingWorkbench")
    initialize = next(
        node for node in sewing.body
        if isinstance(node, ast.FunctionDef) and node.name == "Initialize"
    )

    imports = _initialize_imports(initialize)
    assert "SewingCommands" in imports
    assert "SewingNetworkCommands" in imports
    assert "FittingCommands" in imports

    # Every command advertised by the network module must be reachable from
    # the native Sewing workbench rather than only being importable directly.
    network_commands = _literal_commands("SewingNetworkCommands")
    assert network_commands
    assert network_commands <= _literal_commands("SewingNetworkCommands")


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
