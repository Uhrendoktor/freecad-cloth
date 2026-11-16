# Copyright (C) 2026 FreeCAD Cloth contributors
"""Headless regression coverage for the simulation workbench task-panel contract."""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freecad_cloth.simulation.SimulationGui import SimulationTaskPanel
from tests.support.assertions import require

EXPECTED_MATERIALS = {"Cotton", "Silk", "Denim", "Wool"}
MATERIAL_COMPONENT_COUNT = 3


def test_simulation_task_panel_is_headless_importable() -> None:
    """Expose the four supported material presets without importing FreeCAD GUI."""
    require(
        condition=SimulationTaskPanel.MATERIALS.keys() == EXPECTED_MATERIALS,
        message="The headless task panel must expose the four supported fabric presets.",
    )
    require(
        condition=all(
            len(values) == MATERIAL_COMPONENT_COUNT
            for values in SimulationTaskPanel.MATERIALS.values()
        ),
        message="Each material preset must define stretch, bend, and density values.",
    )


def test_material_presets_have_positive_physical_parameters() -> None:
    """Require every material preset to use positive stretch, bend, and density values."""
    require(
        condition=all(
            stretch > 0 and bend > 0 and density > 0
            for stretch, bend, density in SimulationTaskPanel.MATERIALS.values()
        ),
        message="All material presets must have positive physical parameters.",
    )


def test_task_panel_exposes_freecad_lifecycle_methods_without_gui_import() -> None:
    """Expose the native task-panel lifecycle callbacks to the FreeCAD host."""
    lifecycle_methods = (
        SimulationTaskPanel.accept,
        SimulationTaskPanel.reject,
        SimulationTaskPanel.getStandardButtons,
        SimulationTaskPanel.step,
        SimulationTaskPanel.reset,
    )
    require(
        condition=all(callable(method) for method in lifecycle_methods),
        message="The task panel must expose all five required FreeCAD lifecycle callbacks.",
    )


def test_simulation_status_warns_when_the_drape_target_is_not_ready() -> None:
    """Do not mark a finite simulation as ready while its collision target is missing."""
    panel = SimulationTaskPanel.__new__(SimulationTaskPanel)
    panel.scene = SimpleNamespace(
        FiniteState=True,
        DrapeTarget=object(),
        SimulatedTime=0.0,
        ParticleCount=0,
        Steps=0,
    )
    panel.status = SimpleNamespace()
    updates = []

    def capture_status(label, message, *, state):
        updates.append((label, message, state))

    with patch("freecad_cloth.common.UiDesign.set_status", side_effect=capture_status):
        with patch(
            "freecad_cloth.simulation.DrapeTarget.target_status",
            return_value={
                "state": "missing",
                "message": "No drape target selected",
            },
        ):
            panel._refresh_status()

    require(
        condition=len(updates) == 1 and updates[0][2] == "warning",
        message="A finite scene with a missing drape target must receive warning status.",
    )


if __name__ == "__main__":
    for name, fn in globals().copy().items():
        if name.startswith("test_"):
            fn()
    sys.stdout.write("simulation GUI tests passed\n")
