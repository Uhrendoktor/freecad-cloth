"""Headless regression coverage for the simulation workbench task-panel contract."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from SimulationGui import SIMULATION_UI_LABELS, SimulationTaskPanel


def test_simulation_task_panel_is_headless_importable():
    assert SimulationTaskPanel.MATERIALS.keys() == {"Cotton", "Silk", "Denim", "Wool"}
    assert all(len(values) == 3 for values in SimulationTaskPanel.MATERIALS.values())


def test_material_presets_have_positive_physical_parameters():
    for stretch, bend, density in SimulationTaskPanel.MATERIALS.values():
        assert stretch > 0
        assert bend > 0
        assert density > 0


def test_simulation_task_panel_uses_consistent_action_labels():
    assert SIMULATION_UI_LABELS == {
        "collision_target": "Collision object",
        "simulation_steps": "Steps",
        "run_action": "Run 30 steps",
    }


def test_task_panel_exposes_freecad_lifecycle_methods_without_gui_import():
    assert callable(SimulationTaskPanel.accept)
    assert callable(SimulationTaskPanel.reject)
    assert callable(SimulationTaskPanel.getStandardButtons)
    assert callable(SimulationTaskPanel.step)
    assert callable(SimulationTaskPanel.reset)


if __name__ == "__main__":
    for name, fn in globals().copy().items():
        if name.startswith("test_"):
            fn()
    print("simulation GUI tests passed")
