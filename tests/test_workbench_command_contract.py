"""Headless/static contract checks for Cloth workbench registration.

The file is executable directly by the normal Python test job and intentionally
does not require FreeCAD or Qt. It verifies that the three registered
workbenches keep their command IDs in sync with the command modules they load
lazily and that each workbench exposes one toolbar/menu group.
"""
from __future__ import annotations

import ast
import importlib
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_WORKBENCHES = {
    "ClothPatternWorkbench": {
        "menu": "Cloth Pattern",
        "imports": ("PatternCommands", "PatternMarks"),
        "prefixes": ("ClothPattern_",),
    },
    "ClothSimulationWorkbench": {
        "menu": "Cloth Simulation",
        "imports": ("SimulationCommands",),
        "prefixes": ("ClothSimulation_",),
    },
    "ClothSewingWorkbench": {
        "menu": "Cloth Sewing",
        "imports": ("SewingCommands", "FittingCommands"),
        "prefixes": ("ClothSewing_", "ClothFitting_"),
    },
}


def _load_init_gui():
    spec = importlib.util.spec_from_file_location("cloth_command_contract_init_gui", ROOT / "InitGui.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _command_modules():
    modules = {}
    for name in {name for data in _WORKBENCHES.values() for name in data["imports"]}:
        modules[name] = importlib.import_module(name)
    return modules


def _command_ids(class_name, modules):
    contract = _WORKBENCHES[class_name]
    command_ids = []
    for name in contract["imports"]:
        command_ids.extend(modules[name].COMMANDS)
    return tuple(command_ids)


def test_registered_workbenches_have_expected_names_and_icons():
    module = _load_init_gui()
    for class_name, contract in _WORKBENCHES.items():
        workbench = getattr(module, class_name)
        assert workbench.MenuText == contract["menu"], f"wrong registration name for {class_name}"
        assert Path(workbench.Icon).is_file(), f"missing icon for {class_name}"
        assert workbench.GetClassName(None) == "Gui::PythonWorkbench"


def test_command_ids_exist_and_are_unique():
    modules = _command_modules()
    seen = set()
    for class_name, contract in _WORKBENCHES.items():
        command_ids = _command_ids(class_name, modules)
        assert command_ids, f"{class_name} declares no commands"
        assert len(command_ids) == len(set(command_ids)), f"duplicate command ID in {class_name}"
        overlap = seen.intersection(command_ids)
        assert not overlap, f"command IDs shared across workbenches: {sorted(overlap)}"
        seen.update(command_ids)
        for command_id in command_ids:
            assert any(command_id.startswith(prefix) for prefix in contract["prefixes"]), (
                f"{class_name} command {command_id!r} is not namespaced to its workbench"
            )


def test_initialize_is_lazy_and_declares_one_toolbar_and_menu_group():
    """Importing InitGui must not import command modules before activation."""
    command_names = {name for data in _WORKBENCHES.values() for name in data["imports"]}
    saved_commands = {name: sys.modules.pop(name, None) for name in command_names}
    original_gui = sys.modules.get("FreeCADGui")

    class FakeGui:
        registered = []

        @classmethod
        def addWorkbench(cls, workbench):
            cls.registered.append(workbench)

    sys.modules["FreeCADGui"] = FakeGui
    try:
        _load_init_gui()
        assert [wb.MenuText for wb in FakeGui.registered] == [
            "Cloth Pattern",
            "Cloth Simulation",
            "Cloth Sewing",
        ]
        for name in command_names:
            assert name not in sys.modules, f"{name} was imported eagerly by InitGui"
    finally:
        if original_gui is None:
            sys.modules.pop("FreeCADGui", None)
        else:
            sys.modules["FreeCADGui"] = original_gui
        for name, module in saved_commands.items():
            if module is not None:
                sys.modules[name] = module

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
    modules = _command_modules()
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
        expected_parts = " + ".join(f"{name}.COMMANDS" for name in contract["imports"])
        assert actual_expression == f"tuple({expected_parts})", (
            f"{class_name} command aggregation drifted: expected tuple({expected_parts}), "
            f"got {actual_expression}"
        )
        assert _command_ids(class_name, modules), f"{class_name} command contract is empty"


if __name__ == "__main__":
    test_registered_workbenches_have_expected_names_and_icons()
    test_command_ids_exist_and_are_unique()
    test_initialize_is_lazy_and_declares_one_toolbar_and_menu_group()
    test_declared_command_expression_matches_command_modules()
    print("Workbench command contract checks passed")
