# Copyright (C) 2026 FreeCAD Cloth contributors
"""Minimal protocols shared by simulation lifecycle operations."""

from typing import Protocol


class _ResettableDocument(Protocol):
    """Document operation required when resetting a simulation scene."""

    def recompute(self) -> None:
        """Recompute the document after the simulation state has been reset."""
        ...


class _ResettableSimulationScene(Protocol):
    """Persisted scene members required by the reset operation."""

    Document: _ResettableDocument
    Proxy: object
