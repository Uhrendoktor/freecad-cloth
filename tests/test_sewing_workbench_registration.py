"""Headless contract checks for the native Cloth Sewing registration surface."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_GROUPS = (
    (
        "Sewing Creation",
        (
            "ClothSewing_CreateSeam",
            "ClothSewing_CreateMNSewing",
            "ClothSewing_CreateNetwork",
            "ClothSewing_FreeSewing",
        ),
    ),
    (
        "Sewing Editing",
        (
            "ClothSewing_CreateOperation",
            "ClothSewing_EditOperation",
            "ClothSewing_EditNetwork",
            "ClothSewing_ReverseSeam",
            "ClothSewing_ToggleAlignment",
        ),
    ),
    (
        "Validation & View",
        (
            "ClothSewing_Validate",
            "ClothSewing_RepairSeam",
            "ClothSewing_Show2D",
        ),
    ),
)
EXPECTED_TOOLBAR = (
    "ClothSewing_CreateSeam",
    "ClothSewing_CreateOperation",
    "ClothSewing_Validate",
)


def _load_init_gui():
    spec = importlib.util.spec_from_file_location("cloth_sewing_registration_init_gui", ROOT / "InitGui.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    assert module is not None
    spec.loader.exec_module(module)
    return module


def _all_sewing_commands():
    return tuple(importlib.import_module(name).COMMANDS for name in ("SewingCommands", "SewingNetworkCommands"))


def test_sewing_group_contract_is_complete_and_ordered():
    module = _load_init_gui()
    assert module.SEWING_COMMAND_GROUPS == EXPECTED_GROUPS
    grouped = tuple(command for _name, commands in module.SEWING_COMMAND_GROUPS for command in commands)
    expected = tuple(command for commands in _all_sewing_commands() for command in commands)
    assert grouped == expected
    assert len(grouped) == len(set(grouped))
    assert module.SEWING_TOOLBAR_COMMANDS == EXPECTED_TOOLBAR
    assert set(module.SEWING_TOOLBAR_COMMANDS) <= set(grouped)


def test_sewing_registration_uses_native_grouped_menus_and_small_toolbar():
    module = _load_init_gui()

    class FakeWorkbench:
        def __init__(self):
            self.toolbars = []
            self.menus = []
            self.contexts = []
        def appendToolbar(self, name, commands):
            self.toolbars.append((name, tuple(commands)))
        def appendMenu(self, name, commands):
            self.menus.append((name, tuple(commands)))
        def appendContextMenu(self, name, commands):
            self.contexts.append((name, tuple(commands)))

    wb = object.__new__(module.ClothSewingWorkbench)
    wb.commands = []
    wb._register_groups(EXPECTED_GROUPS, toolbar_name="Cloth Sewing", toolbar_commands=EXPECTED_TOOLBAR)

    assert wb.commands == [command for _name, commands in EXPECTED_GROUPS for command in commands]
    assert wb.toolbars == [("Cloth Sewing", EXPECTED_TOOLBAR)]
    assert wb.menus == [(["Cloth Sewing", name], commands) for name, commands in EXPECTED_GROUPS]
    wb.ContextMenu("view")
    assert wb.contexts == [("Cloth Sewing", tuple(wb.commands))]


def test_sewing_registration_rejects_duplicate_or_out_of_sync_commands():
    module = _load_init_gui()
    expected = [command for _name, commands in EXPECTED_GROUPS[:3] for command in commands]
    valid = list(EXPECTED_GROUPS[:3])
    module._validate_sewing_command_groups(valid, expected)

    duplicate = [("A", (expected[0],)), ("B", (expected[0],))]
    try:
        module._validate_sewing_command_groups(duplicate, expected)
    except ValueError as exc:
        assert "duplicates" in str(exc)
    else:
        raise AssertionError("duplicate command group was accepted")

    incomplete = valid[:-1]
    try:
        module._validate_sewing_command_groups(incomplete, expected)
    except ValueError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("incomplete command groups were accepted")

    extra = valid + [("Extra", ("ClothSewing_Unexpected",))]
    try:
        module._validate_sewing_command_groups(extra, expected)
    except ValueError as exc:
        assert "unexpected" in str(exc)
    else:
        raise AssertionError("unexpected command was accepted")


def test_sewing_initialize_keeps_full_command_surface_in_menus():
    module = _load_init_gui()

    class FakeWorkbench:
        def appendToolbar(self, name, commands):
            self.toolbar = (name, tuple(commands))
        def appendMenu(self, name, commands):
            self.menus = getattr(self, "menus", []) + [(name, tuple(commands))]
        def appendContextMenu(self, name, commands):
            self.context = (name, tuple(commands))

    wb = object.__new__(module.ClothSewingWorkbench)
    wb.commands = []
    wb.MenuText = "Cloth Sewing"
    # Registration itself is deterministic without importing FreeCADGui.
    wb._register_groups(module.SEWING_COMMAND_GROUPS + (("Fitting & Avatar", ()),), toolbar_name="Cloth Sewing", toolbar_commands=EXPECTED_TOOLBAR)
    menu_commands = tuple(command for _name, commands in wb.menus for command in commands)
    assert menu_commands == tuple(wb.commands)
    assert set(EXPECTED_TOOLBAR) <= set(menu_commands)
