# Copyright (C) 2026 FreeCAD Cloth contributors
"""Shared typing contracts for FreeCAD simulation document operations."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from freecad_cloth.common.garment_document import FreeCADDocumentObjectProtocol


class SimulationDocument(Protocol):
    """FreeCAD document operations required by simulation commands."""

    Objects: list[FreeCADDocumentObjectProtocol]

    def addObject(self, object_type: str, name: str) -> FreeCADDocumentObjectProtocol:
        """Create a feature in the document.

        Args:
            object_type: Native FreeCAD feature type identifier.
            name: Stable internal name assigned to the feature.

        Returns:
            The newly created feature object.
        """
        ...

    def getObject(self, object_name: str) -> FreeCADDocumentObjectProtocol | None:
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
    ClothPieces: Sequence[FreeCADDocumentObjectProtocol]
    Proxy: SimulationProxyProtocol


class SimulationProxyProtocol(Protocol):
    """Lifecycle methods available on the simulation feature proxy."""

    def execute(self, obj: SimulationScene) -> None:
        """Recompute the persisted simulation state.

        Args:
            obj: Persisted simulation scene whose inputs and derived state are recomputed.
        """
        ...

    def reset(self, obj: SimulationScene) -> None:
        """Reset transient solver state without changing authored inputs.

        Args:
            obj: Persisted simulation scene whose runtime state is reset.
        """
        ...
