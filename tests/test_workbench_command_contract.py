"""Headless/static contract checks for package-owned workbench registration."""
from __future__ import annotations

import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_WORKBENCHES = {
    "freecad_cloth.pattern.workbench": {
        "class": "ClothPatternWorkbench", "menu": "Cloth Pattern",
        "imports": ("freecad_cloth.pattern.PatternCommands", "freecad_cloth.pattern.PatternMarks"),
        "prefixes": ("ClothPattern_",),
    },
    "freecad_cloth.simulation.workbench": {
        "class": "ClothSimulationWorkbench", "menu": "Cloth Simulation",
        "imports": ("freecad_cloth.simulation.SimulationCommands", "freecad_cloth.simulation.DrapeCommands"),
        "prefixes": ("ClothSimulation_", "ClothDrape_"),
    },
    "freecad_cloth.sewing.workbench": {
        "class": "ClothSewingWorkbench", "menu": "Cloth Sewing",
        "imports": (
            "freecad_cloth.sewing.SewingCommands",
            "freecad_cloth.sewing.SewingNetworkCommands",
            "freecad_cloth.avatar.FittingCommands",
            "freecad_cloth.avatar.AvatarCommands",
        ),
        "prefixes": ("ClothSewing_", "ClothFitting_", "ClothAvatar_"),
    },
}


def test_workbench_modules_are_package_owned_and_importable():
    for module_name, contract in _WORKBENCHES.items():
        module = importlib.import_module(module_name)
        workbench = getattr(module, contract["class"])
        assert workbench.MenuText == contract["menu"]
        assert workbench.GetClassName() == "Gui::PythonWorkbench"
        assert (ROOT / "resources" / "icons" / workbench.Icon).is_file()


def test_command_ids_exist_and_are_unique():
    seen = set()
    for contract in _WORKBENCHES.values():
        for module_name in contract["imports"]:
            module = importlib.import_module(module_name)
            commands = tuple(module.COMMANDS)
            assert commands
            assert len(commands) == len(set(commands))
            assert not seen.intersection(commands)
            seen.update(commands)
            for command_id in commands:
                assert any(command_id.startswith(prefix) for prefix in contract["prefixes"]), command_id


def test_init_gui_is_bootstrap_only():
    source = (ROOT / "InitGui.py").read_text(encoding="utf-8")
    assert "from freecad_cloth.pattern.workbench import ClothPatternWorkbench" in source
    assert "from freecad_cloth.sewing.workbench import" in source
    assert "from freecad_cloth.simulation.workbench import ClothSimulationWorkbench" in source
    for legacy in ("import PatternCommands", "import SewingNetworkCommands", "import SewingNetworkGui", "import SimulationStaleGuard", "import DrapeTarget"):
        assert legacy not in source


def test_all_implementation_python_files_are_inside_package_tree():
    forbidden = {"PatternCommands.py", "SewingNetworkCommands.py", "SewingNetworkGui.py", "SimulationStaleGuard.py", "FittingCommands.py"}
    root_python = {path.name for path in ROOT.glob("*.py")}
    assert root_python <= {"Init.py", "InitGui.py", "sitecustomize.py"}
    assert not root_python.intersection(forbidden)


if __name__ == "__main__":
    for fn in (test_workbench_modules_are_package_owned_and_importable, test_command_ids_exist_and_are_unique, test_init_gui_is_bootstrap_only, test_all_implementation_python_files_are_inside_package_tree):
        fn()
    print("Workbench command contract checks passed")
