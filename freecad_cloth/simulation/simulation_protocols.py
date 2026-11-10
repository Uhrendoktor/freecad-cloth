# Copyright (C) 2026 FreeCAD Cloth contributors
"""Shared typing contracts for FreeCAD simulation document operations."""

from collections.abc import Sequence
from typing import Protocol


class SimulationDocument(Protocol):
    """FreeCAD document operations required by simulation commands."""

    Objects: Sequence[object]

    def addObject(self, type_name: str, object_name: str) -> object:
        """Create a feature in the document.

        Args:
            type_name: Native FreeCAD feature type identifier.
            object_name: Stable internal name assigned to the feature.

        Returns:
            The newly created feature object.
        """
        ...

    def getObject(self, object_name: str) -> object | None:
        """Find a feature by its stable internal name.

        Args:
            object_name: Internal document object name to look up.

        Returns:
            The matching feature or None when it is absent.
        """
        ...

    def recompute(self) -> None:
        """Recompute the document after simulation state changes."""
        ...


class SimulationScene(Protocol):
    """Persisted simulation scene fields required by public lifecycle commands."""

    Steps: int
    Document: SimulationDocument
    ClothPieces: Sequence[object]
    Proxy: object
