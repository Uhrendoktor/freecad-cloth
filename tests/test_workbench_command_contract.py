"""Headless/static contract checks for package-owned workbench registration."""

import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_WORKBENCHES = {
    "freecad_cloth.pattern.workbench": ("ClothPatternWorkbench", "Cloth Pattern", ("freecad_cloth.pattern.PatternCommands", "freecad_cloth.pattern.PatternMarks")),
    "freecad_cloth.simulation.workbench": ("ClothSimulationWorkbench", "Cloth Simulation", ("freecad_cloth.simulation.SimulationCommands", "freecad_cloth.simulation.DrapeCommands")),
    "freecad_cloth.sewing.workbench": ("ClothSewingWorkbench", "Cloth Sewing", ("freecad_cloth.sewing.SewingCommands", "freecad_cloth.sewing.SewingNetworkCommands", "freecad_cloth.avatar.FittingCommands", "freecad_cloth.avatar.AvatarCommands")),
}


def test_workbench_modules_are_package_owned_and_importable():
    for module_name, (class_name, menu, modules) in _WORKBENCHES.items():
        module = importlib.import_module(module_name)
        workbench = getattr(module, class_name)()
        assert workbench.MenuText == menu
        assert workbench.GetClassName() == "Gui::PythonWorkbench"
        assert Path(workbench.Icon).is_file()
        assert workbench.commands == []
        for command_module in modules:
            assert importlib.import_module(command_module).COMMANDS


def test_command_ids_exist_and_are_unique():
    seen = set()
    for contract in _WORKBENCHES.values():
        for module_name in contract[2]:
            commands = tuple(importlib.import_module(module_name).COMMANDS)
            assert len(commands) == len(set(commands))
            assert not seen.intersection(commands)
            seen.update(commands)


def test_init_gui_is_bootstrap_only():
    source = (ROOT / "InitGui.py").read_text(encoding="utf-8")
    assert "from freecad_cloth.pattern.workbench import ClothPatternWorkbench" in source
    assert "from freecad_cloth.sewing.workbench import ClothSewingWorkbench" in source
    assert "from freecad_cloth.simulation.workbench import ClothSimulationWorkbench" in source
    for legacy in ("import PatternCommands", "import SewingNetworkCommands", "import SewingNetworkGui", "import SimulationStaleGuard", "import DrapeTarget"):
        assert legacy not in source


def test_all_implementation_python_files_are_inside_package_tree():
    forbidden = {"PatternCommands.py", "SewingNetworkCommands.py", "SewingNetworkGui.py", "SimulationStaleGuard.py", "FittingCommands.py"}
    root_python = {path.name for path in ROOT.glob("*.py")}
    assert root_python <= {"Init.py", "InitGui.py", "sitecustomize.py"}
    assert not root_python.intersection(forbidden)
