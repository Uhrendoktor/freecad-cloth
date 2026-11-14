# Copyright (C) 2026 FreeCAD Cloth contributors
"""Canonical static types for the authored MakeHuman skeleton payload."""

from typing import NotRequired, TypedDict


class BoneData(TypedDict):
    """Fields used by the avatar rig for one authored bone."""

    head: str
    tail: str
    parent: NotRequired[str | None]


class SkeletonData(TypedDict):
    """Joint vertex memberships and referencing bones from the pinned source asset."""

    bones: dict[str, BoneData]
    joints: dict[str, list[int]]
