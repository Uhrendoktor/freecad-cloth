"""Shared, FreeCAD-independent contracts used by all Cloth workbenches."""

from .collision import CollisionSurface
from .targets import DrapeTargetRef

__all__ = ["CollisionSurface", "DrapeTargetRef"]
