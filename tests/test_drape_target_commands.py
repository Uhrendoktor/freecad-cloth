# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression contract for mannequin drape-target attachment."""

import sys
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
