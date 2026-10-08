"""Behavioral checks for the FreeCAD GUI registration boundary.

GUI rendering itself belongs to FreeCAD end-to-end coverage. This suite tests the
Python-side registration data and registration behavior directly instead of
searching implementation source text for UI strings.
"""

from pathlib import Path

from freecad_cloth.avatar import AvatarCommands
from freecad_cloth.avatar.AvatarGui import AvatarTaskPanel
from freecad_cloth.avatar.AvatarPoseGui import SkeletonPoseController
from freecad_cloth.pattern import PatternCommands
from freecad_cloth.sewing.workbench import (
    COMMAND_GROUPS as SEWING_COMMAND_GROUPS,
    TOOLBAR_COMMANDS as SEWING_TOOLBAR_COMMANDS,
    ClothSewingWorkbench,
    _validate_sewing_command_groups,
)
from freecad_cloth.simulation import SimulationCommands
from freecad_cloth.gui import ClothWorkbenchBase


ROOT = Path(__file__).resolve().parents[1]


def test_workbench_base_resources_and_lifecycle_contract():
    workbench = ClothWorkbenchBase.__new__(ClothWorkbenchBase)
    workbench.MenuText = "Cloth"
    workbench.ToolTip = "Cloth workbench"
    workbench.Icon = "icon.svg"
    workbench.commands = []
    assert workbench.GetResources() == {
        "MenuText": "Cloth",
        "ToolTip": "Cloth workbench",
        "Icon": "icon.svg",
    }
    assert workbench.GetClassName() == "Gui::PythonWorkbench"
    assert workbench.Activated() is None
    assert workbench.Deactivated() is None


def test_sewing_command_groups_are_unique_and_complete():
    groups = dict(SEWING_COMMAND_GROUPS)
    assert tuple(groups) == (
        "Sewing Creation",
        "Sewing Editing",
        "Validation & View",
        "Fitting & Avatar",
    )
    assert groups["Fitting & Avatar"] == ()
    commands = [command for group in groups.values() for command in group]
    assert len(commands) == len(set(commands))
    assert commands == [
        "ClothSewing_CreateSeam",
        "ClothSewing_CreateMNSewing",
        "ClothSewing_CreateNetwork",
        "ClothSewing_FreeSewing",
        "ClothSewing_CreateOperation",
        "ClothSewing_EditOperation",
        "ClothSewing_EditNetwork",
        "ClothSewing_ReverseSeam",
        "ClothSewing_ToggleAlignment",
        "ClothSewing_Validate",
        "ClothSewing_RepairSeam",
        "ClothSewing_FocusSeam3D",
        "ClothSewing_EditSeamSideA",
        "ClothSewing_EditSeamSideB",
        "ClothSewing_Show2D",
    ]


def test_sewing_toolbar_is_a_unique_subset_of_registered_commands():
    grouped = {command for _group, commands in SEWING_COMMAND_GROUPS for command in commands}
    assert set(SEWING_TOOLBAR_COMMANDS) <= grouped
    assert len(SEWING_TOOLBAR_COMMANDS) == len(set(SEWING_TOOLBAR_COMMANDS))


def test_sewing_registration_uses_nested_menus_and_toolbar_subset(monkeypatch):
    import freecad_cloth.gui as gui_module

    monkeypatch.setattr(gui_module, "Gui", object())
    workbench = ClothSewingWorkbench()
    calls = []
    workbench.appendToolbar = lambda name, commands: calls.append(("toolbar", name, list(commands)))
    workbench.appendMenu = lambda name, commands: calls.append(("menu", name, list(commands)))
    workbench._register_groups(
        SEWING_COMMAND_GROUPS,
        toolbar_name=workbench.MenuText,
        toolbar_commands=SEWING_TOOLBAR_COMMANDS,
    )
    assert calls[0] == ("toolbar", "Cloth Sewing", list(SEWING_TOOLBAR_COMMANDS))
    assert calls[1:] == [
        ("menu", ["Cloth Sewing", "Sewing Creation"], list(SEWING_COMMAND_GROUPS[0][1])),
        ("menu", ["Cloth Sewing", "Sewing Editing"], list(SEWING_COMMAND_GROUPS[1][1])),
        ("menu", ["Cloth Sewing", "Validation & View"], list(SEWING_COMMAND_GROUPS[2][1])),
    ]


def test_sewing_command_group_validator_rejects_invalid_groups():
    expected = ["one", "two", "three"]
    _validate_sewing_command_groups((("A", ("one",)), ("B", ("two", "three"))), expected)
    cases = [
        ((("A", ("one",)), ("B", ("two",))), "missing: three"),
        ((("A", ("one", "two")), ("B", ("two", "three"))), "duplicates"),
        ((("A", ("one",)), ("B", ("two", "three")), ("C", ("extra",))), "unexpected"),
    ]
    for groups, marker in cases:
        try:
            _validate_sewing_command_groups(groups, expected)
        except ValueError as exc:
            assert marker in str(exc)
        else:
            raise AssertionError(f"invalid command groups were accepted: {marker}")


def test_workbench_registration_is_idempotent():
    import freecad_cloth.gui as gui_module

    monkeypatch = type("_MonkeyPatch", (), {})()
    original_gui = gui_module.Gui
    gui_module.Gui = object()
    try:
        workbench = ClothSewingWorkbench()
        calls = []
        workbench.appendToolbar = lambda name, commands: calls.append(("toolbar", name, list(commands)))
        workbench.appendMenu = lambda name, commands: calls.append(("menu", name, list(commands)))
        workbench._register_groups(SEWING_COMMAND_GROUPS, toolbar_name=workbench.MenuText)
        first_calls = list(calls)
        workbench._register_groups(SEWING_COMMAND_GROUPS, toolbar_name=workbench.MenuText)
        assert calls == first_calls
        assert workbench.commands == [
            command for _group, commands in SEWING_COMMAND_GROUPS for command in commands
        ]
    finally:
        gui_module.Gui = original_gui


def test_public_command_surfaces_are_nonempty_and_unique():
    for module in (PatternCommands, SimulationCommands, AvatarCommands):
        commands = tuple(module.COMMANDS)
        assert commands
        assert len(commands) == len(set(commands))
        assert all(command.startswith("Cloth") for command in commands)


def test_public_command_surfaces_preserve_authoring_boundaries():
    assert "ClothPattern_CreateDrafting" not in PatternCommands.COMMANDS
    assert {
        "ClothPattern_EditSketch",
        "ClothPattern_CreateSketch",
        "ClothPattern_CreateFromSketch",
        "ClothPattern_SurfacePen",
    } <= set(PatternCommands.COMMANDS)
    assert {
        "ClothSimulation_Edit",
        "ClothSimulation_Step",
        "ClothSimulation_Run",
        "ClothSimulation_Reset",
    } <= set(SimulationCommands.COMMANDS)
    assert {
        "ClothFitting_CreateAvatar",
        "ClothFitting_EditAvatar",
        "ClothFitting_PoseAvatar",
    } <= set(AvatarCommands.COMMANDS)


def test_avatar_gui_schema_matches_authoritative_command_mapping():
    assert AvatarTaskPanel.PROPERTY_MAP == AvatarCommands.PROPERTY_MAP
    assert tuple(key for key, _label in AvatarTaskPanel.PROVIDERS) == AvatarCommands.PROVIDER_IDS
    assert {key for key, _label in AvatarTaskPanel.POSE_FIELDS} == {
        "left_arm_angle",
        "right_arm_angle",
        "left_elbow_angle",
        "right_elbow_angle",
    }


def test_pose_projection_distance_has_stable_boundary_behavior():
    distance = SkeletonPoseController._screen_segment_distance
    assert distance((5, 0), (0, 0), (10, 0)) == 0.0
    assert distance((5, 3), (0, 0), (10, 0)) == 3.0
    assert distance((20, 0), (0, 0), (10, 0)) == 10.0
    assert distance((5, 0), (5, 0), (5, 0)) == 0.0


def test_workbench_icons_are_present_and_valid_svg_resources():
    for name in (
        "ClothPattern.svg",
        "ClothSimulation.svg",
        "ClothSewing.svg",
        "ClothPattern_SurfacePen.svg",
    ):
        path = ROOT / "resources" / "icons" / name
        assert path.is_file(), path
        content = path.read_text(encoding="utf-8").lstrip()
        assert content.startswith("<svg "), path
        assert 'xmlns="http://www.w3.org/2000/svg"' in content
