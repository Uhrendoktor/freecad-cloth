"""Headless regression coverage for the simulation workbench task-panel contract."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freecad_cloth.simulation.SimulationGui import SimulationTaskPanel


def test_simulation_task_panel_is_headless_importable():
    assert SimulationTaskPanel.MATERIALS.keys() == {"Cotton", "Silk", "Denim", "Wool"}
    assert all(len(values) == 3 for values in SimulationTaskPanel.MATERIALS.values())


def test_material_presets_have_positive_physical_parameters():
    for stretch, bend, density in SimulationTaskPanel.MATERIALS.values():
        assert stretch > 0
        assert bend > 0
        assert density > 0


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


def test_task_panels_expose_reversible_arrange_fit_bridge():
    from freecad_cloth.simulation.SimulationQualityGui import SimulationQualityTaskPanel
    from freecad_cloth.simulation.FittingHandoff import (
        fitting_stage_status,
        open_arrange_fit_from_simulation,
        reset_arrangement_from_simulation,
    )

    assert callable(SimulationQualityTaskPanel.open_arrange_fit)
    assert callable(SimulationQualityTaskPanel.reset_arrangement)
    assert callable(fitting_stage_status)
    assert callable(open_arrange_fit_from_simulation)
    assert callable(reset_arrangement_from_simulation)


def test_arrange_fit_bridge_uses_existing_fitting_stage_contract():
    source = (
        Path(__file__).resolve().parents[1]
        / "freecad_cloth"
        / "simulation"
        / "FittingHandoff.py"
    ).read_text(encoding="utf-8")
    assert "does not introduce placement heuristics" in source
    assert "add_selected_pattern_pieces" in source
    assert "assign_avatar_source" in source
    assert 'Gui.activateWorkbench("Cloth Sewing")' in source
