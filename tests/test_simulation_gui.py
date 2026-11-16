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


class _ViewportSelection:
    """Capture native selection changes requested by viewport helper buttons."""

    def __init__(self) -> None:
        self.items = []
        self.calls = []

    def clearSelection(self) -> None:
        self.items.clear()
        self.calls.append(("clear",))

    def addSelection(self, obj) -> None:
        self.items.append(obj)
        self.calls.append(("select", obj))


def _viewport_panel():
    """Build a headless simulation panel with selected cloth/target document objects."""
    cloth = SimpleNamespace(Name="PatternFront", Label="Front panel")
    target_source = SimpleNamespace(Name="AvatarBody", Label="Cloth mannequin")
    target = SimpleNamespace(Name="DrapeTarget", SourceObject=target_source)
    objects = {obj.Name: obj for obj in (cloth, target_source, target)}
    document = SimpleNamespace(getObject=lambda name: objects.get(str(name)))
    panel = SimulationTaskPanel.__new__(SimulationTaskPanel)
    panel.App = SimpleNamespace(ActiveDocument=document)
    panel.scene = SimpleNamespace(Document=document)
    panel.cloth = SimpleNamespace(currentData=lambda: "PatternFront")
    panel.target = SimpleNamespace(currentData=lambda: "DrapeTarget")
    panel.Gui = SimpleNamespace(Selection=_ViewportSelection())
    panel.status = SimpleNamespace()
    return panel, cloth, target_source


def test_simulation_scene_selectors_highlight_the_selected_objects_in_3d() -> None:
    """Select the cloth piece and the target's linked source without moving the camera."""
    panel, cloth, target_source = _viewport_panel()
    updates = []

    with patch(
        "freecad_cloth.common.UiDesign.set_status",
        side_effect=lambda label, message, *, state: updates.append((message, state)),
    ):
        require(
            condition=panel._select_cloth_in_viewport() is True,
            message="The selected cloth object must be selectable in the viewport.",
        )
        require(
            condition=panel._select_target_source_in_viewport() is True,
            message="The target action must highlight its linked collision source.",
        )

    require(
        condition=panel.Gui.Selection.calls
        == [
            ("clear",),
            ("select", cloth),
            ("clear",),
            ("select", target_source),
        ],
        message="Viewport actions must select the chosen cloth and target source only.",
    )
    require(
        condition=all(state == "info" for _message, state in updates),
        message="Successful viewport selection must report informational status.",
    )
    require(
        condition="camera position is unchanged" in updates[-1][0],
        message="Viewport highlighting must not reorient the camera.",
    )


def test_simulation_viewport_actions_are_disabled_without_valid_selection() -> None:
    """Disable select-in-3D buttons when the corresponding selector has no object."""
    panel, _cloth, _target_source = _viewport_panel()
    panel.cloth = SimpleNamespace(currentData=lambda: "")
    panel.target = SimpleNamespace(currentData=lambda: "MissingTarget")
    states = []
    panel.cloth_view_button = SimpleNamespace(setEnabled=states.append)
    panel.target_view_button = SimpleNamespace(setEnabled=states.append)

    panel._refresh_viewport_actions()

    require(
        condition=states == [False, False],
        message="Both viewport actions must be disabled without resolvable scene objects.",
    )


def test_simulation_target_viewport_action_rejects_missing_source() -> None:
    """Do not highlight the metadata feature when its Drape Target has no source."""
    target = SimpleNamespace(Name="DrapeTarget", SourceObject=None)
    document = SimpleNamespace(getObject=lambda name: target if name == "DrapeTarget" else None)
    panel = SimulationTaskPanel.__new__(SimulationTaskPanel)
    panel.App = SimpleNamespace(ActiveDocument=document)
    panel.scene = SimpleNamespace(Document=document)
    panel.target = SimpleNamespace(currentData=lambda: "DrapeTarget")
    panel.Gui = SimpleNamespace(Selection=_ViewportSelection())
    panel.status = SimpleNamespace()
    updates = []

    with patch(
        "freecad_cloth.common.UiDesign.set_status",
        side_effect=lambda label, message, *, state: updates.append((message, state)),
    ):
        require(
            condition=panel._select_target_source_in_viewport() is False,
            message="The target action must fail when there is no linked source.",
        )

    require(
        condition=panel.Gui.Selection.calls == [],
        message="A missing target source must not alter FreeCAD's current selection.",
    )
    require(
        condition=updates and updates[-1][1] == "warning",
        message="The missing-source state must be visible as a warning.",
    )


if __name__ == "__main__":
    for name, fn in globals().copy().items():
        if name.startswith("test_"):
            fn()
    sys.stdout.write("simulation GUI tests passed\n")
