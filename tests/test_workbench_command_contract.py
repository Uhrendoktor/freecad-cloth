"""Headless/static contract checks for Cloth workbench registration.

These checks intentionally do not require FreeCAD or Qt.  They verify that the
three registered workbenches keep their command IDs in sync with the command
modules they load lazily and that each workbench exposes one toolbar/menu group.
"""
from __future__ import annotations

import ast
import importlib
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_WORKBENCHES = {
    "ClothPatternWorkbench": {
        "menu": "Cloth Pattern",
        "imports": ("PatternCommands", "PatternMarks"),
        "command_expr": "PatternCommands.COMMANDS + PatternMarks.COMMANDS",
    },
    "ClothSimulationWorkbench": {
        "menu": "Cloth Simulation",
        "imports": ("SimulationCommands",),
        "command_expr": "SimulationCommands.COMMANDS",
    },
    "ClothSewingWorkbench": {
        "menu": "Cloth Sewing",
        "imports": ("SewingCommands", "FittingCommands"),
        "command_expr": "SewingCommands.COMMANDS + FittingCommands.COMMANDS",
    },
}


def _load_init_gui():
    spec = importlib.util.spec_from_file_location("cloth_command_contract_init_gui", ROOT / "InitGui.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _initialize_command_modules():
    modules = {}
    for name in {name for data in _WORKBENCHES.values() for name in data["imports"]}:
        modules[name] = importlib.import_module(name)
    return modules


def _workbench_classes():
    module = _load_init_gui()
    return {name: getattr(module, name) for name in _WORKBENCHES}


def test_registered_workbenches_have_expected_names_and_icons():
    classes = _workbench_classes()
    assert set(classes) == set(_WORKBENCHES)
    for class_name, contract in _WORKBENCHES.items():
        workbench = classes[class_name]
        assert workbench.MenuText == contract["menu"], f"wrong registration name for {class_name}"
        assert Path(workbench.Icon).is_file(), f"missing icon for {class_name}"
        assert workbench.GetClassName(None) == "Gui::PythonWorkbench"


def test_command_ids_exist_and_are_unique():
    modules = _initialize_command_modules()
    seen = set()
    for class_name, contract in _WORKBENCHES.items():
        if class_name == "ClothPatternWorkbench":
            command_ids = tuple(modules["PatternCommands"].COMMANDS) + tuple(modules["PatternMarks"].COMMANDS)
        elif class_name == "ClothSimulationWorkbench":
            command_ids = tuple(modules["SimulationCommands"].COMMANDS)
        else:
            command_ids = tuple(modules["SewingCommands"].COMMANDS) + tuple(modules["FittingCommands"].COMMANDS)

        assert command_ids, f"{class_name} declares no commands"
        assert len(command_ids) == len(set(command_ids)), f"duplicate command ID in {class_name}"
        overlap = seen.intersection(command_ids)
        assert not overlap, f"command IDs shared across workbenches: {sorted(overlap)}"
        seen.update(command_ids)

        for command_id in command_ids:
            assert command_id.startswith(class_name.removesuffix("Workbench") + "_"), (
                f"{class_name} command {command_id!r} is not namespaced to its workbench"
            )


def test_initialize_is_lazy_and_declares_one_toolbar_and_menu_group(monkeypatch):
    """Importing InitGui must not import command modules before activation."""
    for name in {name for data in _WORKBENCHES.values() for name in data["imports"]}:
        sys.modules.pop(name, None)

    class FakeGui:
        registered = []

        @classmethod
        def addWorkbench(cls, workbench):
            cls.registered.append(workbench)

    monkeypatch.setitem(sys.modules, "FreeCADGui", FakeGui)
    module = _load_init_gui()

    assert [wb.MenuText for wb in FakeGui.registered] == [
        "Cloth Pattern",
        "Cloth Simulation",
        "Cloth Sewing",
    ]
    for name in {name for data in _WORKBENCHES.values() for name in data["imports"]}:
        assert name not in sys.modules, f"{name} was imported eagerly by InitGui"

    source = ast.parse((ROOT / "InitGui.py").read_text())
    classes = {node.name: node for node in source.body if isinstance(node, ast.ClassDef)}
    for class_name, contract in _WORKBENCHES.items():
        node = classes[class_name]
        initialize = next(
            method for method in node.body
            if isinstance(method, ast.FunctionDef) and method.name == "Initialize"
        )
        initialize_source = ast.get_source_segment(source, initialize) or ""
        for module_name in contract["imports"]:
            assert f"import {module_name}" in initialize_source, (
                f"{class_name}.Initialize must lazily import {module_name}"
            )
        assert "self.appendToolbar(self.MenuText, self.commands)" in initialize_source, (
            f"{class_name} must declare its toolbar group"
        )
        assert "self.appendMenu(self.MenuText, self.commands)" in initialize_source, (
            f"{class_name} must declare its menu group"
        )


def test_declared_command_expression_matches_command_modules():
    """Keep each Initialize command aggregation synchronized with COMMANDS."""
    modules = _initialize_command_modules()
    source = ast.parse((ROOT / "InitGui.py").read_text())

    for class_name, contract in _WORKBENCHES.items():
        node = next(n for n in source.body if isinstance(n, ast.ClassDef) and n.name == class_name)
        initialize = next(n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == "Initialize")
        assignment = next(
            n for n in ast.walk(initialize)
            if isinstance(n, ast.Assign)
            and any(isinstance(target, ast.Attribute) and target.attr == "commands" for target in n.targets)
        )
        actual_expression = ast.unparse(assignment.value)
        assert actual_expression == f"tuple({contract['command_expr']})", (
            f"{class_name} command aggregation drifted: expected tuple({contract['command_expr']}), "
            f"got {actual_expression}"
        )

        namespace = {name: modules[name] for name in contract["imports"]}
        expected = eval(contract["command_expr"], {}, namespace)
        assert expected, f"{class_name} command contract is empty"


@pytest.fixture(autouse=True)
def _restore_gui_module():
    """Prevent the fake FreeCADGui module from leaking between tests."""
    original = sys.modules.get("FreeCADGui")
    yield
    if original is None:
        sys.modules.pop("FreeCADGui", None)
    else:
        sys.modules["FreeCADGui"] = original
