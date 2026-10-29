# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression checks for avatar-driven fitting anchor refresh routing."""

from types import SimpleNamespace
from unittest.mock import Mock

from freecad_cloth.avatar.FittingCommands import refresh_avatar_anchor_positions
from tests.support.assertions import require


def test_anchor_refresh_skips_a_target_owned_by_another_object() -> None:
    """Skip refresh when the persistent target does not reference this avatar."""
    avatar = object()
    scene = SimpleNamespace(FittingType="FittingScene", Document=SimpleNamespace())
    target = SimpleNamespace(SourceObject=object())
    document = SimpleNamespace(Objects=(scene,), getObject=Mock(return_value=target))

    refreshed_names = refresh_avatar_anchor_positions(document, avatar)

    require(
        condition=refreshed_names == (),
        message="Fitting anchors must not refresh for a different target source.",
    )
    require(
        condition=document.getObject.call_args.args == ("DrapeTarget",),
        message="Anchor refresh must check the document's persistent drape target.",
    )
