"""Headless/static contract checks for Cloth workbench registration."""
from __future__ import annotations

import ast
import importlib
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_WORKBENCHES = {
    "ClothPatternWorkbench": {"menu": "Cloth Pattern", "imports": ("PatternCommands", "PatternMarks"), "prefixes": ("ClothPattern_",)},
    "ClothSimulationWorkbench": {"menu": "Cloth Simulation", "imports": ("SimulationCommands",), "prefixes": ("ClothSimulation_",)},
    "ClothSewingWorkbench": {"menu": "Cloth Sewing", "imports": ("SewingCommands", "FittingCommands"), "prefixes": ("ClothSewing_", "ClothFitting_")},
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
    ids = []
    for name in _WORKBENCHES[class_name]["imports"]:
        ids.extend(modules[name].COMMANDS)
    return tuple(ids)


def test_registered_workbenches_have_expected_names_and_icons():
    module = _load_init_gui()
    for class_name, contract in _WORKBENCHES.items():
        workbench = getattr(module, class_name)
        assert workbench.MenuText == contract["menu"]
        assert (ROOT / "resources" / "icons" / workbench.Icon).is_file(), f"missing icon for {class_name}"
        assert workbench.GetClassName(None) == "Gui::PythonWorkbench"


def test_command_ids_exist_and_are_unique():
    modules = _command_modules()
    seen = set()
    for class_name, contract in _WORKBENCHES.items():
        command_ids = _command_ids(class_name, modules)
        assert command_ids
        assert len(command_ids) == len(set(command_ids))
        assert not seen.intersection(command_ids)
        seen.update(command_ids)
        for command_id in command_ids:
            assert any(command_id.startswith(prefix) for prefix in contract["prefixes"]), command_id


def test_initialize_is_lazy_and_declares_one_toolbar_and_menu_group():
    command_names = {name for data in _WORKBENCHES.values() for name in data["imports"]}
    saved_commands = {name: sys.modules.pop(name, None) for name in command_names}
    original_gui = sys.modules.get("FreeCADGui")

    class FakeWorkbench:
        def appendToolbar(self, name, commands):
            self._toolbar = (name, list(commands))
        def appendMenu(self, name, commands):
            self._menu = (name, list(commands))
        def appendContextMenu(self, name, commands):
            self._context = (name, list(commands))

    class FakeGui:
        Workbench = FakeWorkbench
        registered = []
        @classmethod
        def addIconPath(cls, path):
            cls.icon_path = path
        @classmethod
        def addWorkbench(cls, workbench):
            cls.registered.append(workbench)

    sys.modules["FreeCADGui"] = FakeGui
    try:
        _load_init_gui()
        assert [wb.MenuText for wb in FakeGui.registered] == ["Cloth Pattern", "Cloth Simulation", "Cloth Sewing"]
        for name in command_names:
            assert name not in sys.modules
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
        initialize = next(n for n in classes[class_name].body if isinstance(n, ast.FunctionDef) and n.name == "Initialize")
        text = ast.get_source_segment(source, initialize) or ""
        for module_name in contract["imports"]:
            assert f"import {module_name}" in text
        assert "self._register(" in text
        assert "self.appendToolbar(self.MenuText, self.commands)" in ast.get_source_segment(source, classes[class_name])
        assert "self.appendMenu(self.MenuText, self.commands)" in ast.get_source_segment(source, classes[class_name])


def test_declared_command_expression_matches_command_modules():
    modules = _command_modules()
    source = ast.parse((ROOT / "InitGui.py").read_text())
    for class_name, contract in _WORKBENCHES.items():
        node = next(n for n in source.body if isinstance(n, ast.ClassDef) and n.name == class_name)
        initialize = next(n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == "Initialize")
        register_call = next(
            n for n in ast.walk(initialize)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "_register"
        )
        actual = ast.unparse(register_call.args[0])
        expected = " + ".join(f"{name}.COMMANDS" for name in contract["imports"])
        assert actual == expected
        assert _command_ids(class_name, modules)


if __name__ == "__main__":
    for fn in (test_registered_workbenches_have_expected_names_and_icons, test_command_ids_exist_and_are_unique, test_initialize_is_lazy_and_declares_one_toolbar_and_menu_group, test_declared_command_expression_matches_command_modules):
        fn()
    print("Workbench command contract checks passed")
