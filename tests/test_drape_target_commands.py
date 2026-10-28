# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression contract for mannequin drape-target attachment."""

import sys
from collections.abc import Callable
from types import ModuleType, SimpleNamespace

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
    setattr(freecad_module, "ActiveDocument", document)
    monkeypatch.setitem(sys.modules, "FreeCAD", freecad_module)

    avatar_module = ModuleType("freecad_cloth.avatar.AvatarCommands")
    setattr(avatar_module, "create_avatar", lambda: mannequin)
    monkeypatch.setitem(sys.modules, "freecad_cloth.avatar.AvatarCommands", avatar_module)

    drape_target_module = ModuleType("freecad_cloth.simulation.DrapeTarget")
    setattr(drape_target_module, "DEFAULT_MANNEQUIN_COLLISION_THICKNESS_MM", 2.0)
    setattr(drape_target_module, "assign_drape_target", lambda *args: None)
    setattr(drape_target_module, "create_drape_target", lambda *args: target)
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

def test_drape_command_exposes_freecad_callback_names() -> None:
    """Keep the host's callback spellings available on the command instance."""
    calls: list[str] = []
    command = DrapeCommands._DrapeCommand(
        "ClothDrape_Diagnostics",
        lambda: calls.append("activated") or "done",
        lambda: True,
        "diagnostic command fixture",
    )
    activated = cast("Callable[[], object]", getattr(command, "Activated"))
    is_active = cast("Callable[[], bool]", getattr(command, "IsActive"))
    get_resources = cast("Callable[[], dict[str, object]]", getattr(command, "GetResources"))

    require(
        condition=activated() == "done" and calls == ["activated"],
        message="FreeCAD's Activated callback must invoke the registered action.",
    )
    require(
        condition=is_active() is True,
        message="FreeCAD's IsActive callback must return the enabled state.",
    )
    resources = get_resources()
    require(
        condition=resources["MenuText"] == "Cloth Diagnostics",
        message="FreeCAD's GetResources callback must preserve the diagnostic menu label.",
    )
    require(
        condition=resources["ToolTip"] == "diagnostic command fixture",
        message="FreeCAD's GetResources callback must preserve the action tooltip.",
    )

