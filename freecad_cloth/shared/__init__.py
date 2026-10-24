# Copyright (C) 2026 FreeCAD Cloth contributors
"""Shared, FreeCAD-independent contracts used by all Cloth workbenches."""

from .Collision import CollisionSurface
from .Targets import DrapeTargetRef

__all__ = ["CollisionSurface", "DrapeTargetRef"]
