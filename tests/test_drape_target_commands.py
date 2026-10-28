# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression contract for mannequin drape-target attachment and command callbacks."""

import sys
from collections.abc import Callable
from types import ModuleType, SimpleNamespace
from typing import cast

import pytest

from freecad_cloth.simulation import DrapeCommands
from tests.support.assertions import require


def test_mannequin_target_attaches_to_simulation_scene(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure mannequin target creation attaches one persistent target to each scene.

    Args:
        monkeypatch: Isolated module substitutions for the FreeCAD host boundary.
    """
    scene = SimpleNamespace(
        Name="ClothSimulation",
        Proxy=SimpleNamespace(Type="ClothSimulation"),
        DrapeTarget=None,
    )
    mannequin = SimpleNamespace(AvatarType="ClothAvatar")
    target = SimpleNamespace(
        CollisionDeflection=1.0,
        CollisionThickness=2.0,
        Label="",
    )

    document = SimpleNamespace(
        Objects=[scene],
        getObject=lambda name: mannequin if name == "ClothAvatar" else None,
        recompute=lambda: None,
    )
    freecad_module = ModuleType("FreeCAD")
    freecad_module.__dict__["ActiveDocument"] = document
    monkeypatch.setitem(sys.modules, "FreeCAD", freecad_module)

    avatar_module = ModuleType("freecad_cloth.avatar.AvatarCommands")
    avatar_module.__dict__["create_avatar"] = lambda: mannequin
    monkeypatch.setitem(sys.modules, "freecad_cloth.avatar.AvatarCommands", avatar_module)

    drape_target_module = ModuleType("freecad_cloth.simulation.DrapeTarget")
    drape_target_module.__dict__["DEFAULT_MANNEQUIN_COLLISION_THICKNESS_MM"] = 2.0
    drape_target_module.__dict__["assign_drape_target"] = lambda *_args: None
    drape_target_module.__dict__["create_drape_target"] = lambda *_args: target
    monkeypatch.setitem(sys.modules, "freecad_cloth.simulation.DrapeTarget", drape_target_module)

    created = DrapeCommands.create_mannequin_drape_target()

    require(
        condition=created is target,
        message="Mannequin-target creation must return the persistent target.",
    )
    require(
        condition=scene.DrapeTarget is target,
        message="Every simulation scene must receive the created persistent target.",
    )
    require(
        condition=target.Label == "Drape Target (Mannequin)",
        message="The created target must retain its mannequin-specific label.",
    )


def test_drape_command_exposes_freecad_callback_names(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify public registration preserves FreeCAD's native command callback interface.

    Args:
        monkeypatch: Isolated FreeCAD host modules for command activation.
    """
    target = SimpleNamespace(Enabled=False)
    document = SimpleNamespace(
        getObject=lambda name: target if name == "DrapeTarget" else None,
        recompute=lambda: None,
    )
    freecad_module = ModuleType("FreeCAD")
    freecad_module.__dict__["ActiveDocument"] = document
    monkeypatch.setitem(sys.modules, "FreeCAD", freecad_module)

    registered_commands: dict[str, object] = {}

    def add_command(name: str, command: object) -> None:
        """Capture a command adapter passed to the public registration API.

        Args:
            name: Stable internal command identifier.
            command: Adapter registered under that identifier.
        """
        registered_commands[name] = command

    gui = SimpleNamespace(addCommand=add_command)
    require(
        condition=DrapeCommands.register_gui_commands(gui),
        message="Command registration must accept the supported FreeCAD GUI boundary.",
    )
    command = registered_commands["ClothDrape_EnableTarget"]
    activated_name = "Activated"
    is_active_name = "IsActive"
    resources_name = "GetResources"
    activated = cast("Callable[[], object]", getattr(command, activated_name))
    is_active = cast("Callable[[], bool]", getattr(command, is_active_name))
    get_resources = cast("Callable[[], dict[str, object]]", getattr(command, resources_name))

    require(
        condition=is_active() is True,
        message="The native IsActive callback must report an active document.",
    )
    require(
        condition=activated() is target and target.Enabled is True,
        message="The native Activated callback must enable the persistent target.",
    )
    resources = get_resources()
    require(
        condition=resources["MenuText"] == "Enable Target",
        message="The native GetResources callback must retain the command label.",
    )
    require(
        condition=resources["ToolTip"] == "Enable the persistent drape target",
        message="The native GetResources callback must retain the command tooltip.",
    )
