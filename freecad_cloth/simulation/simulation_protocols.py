# Copyright (C) 2026 FreeCAD Cloth contributors
"""Shared typing contracts for FreeCAD simulation document operations."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, Self

from freecad_cloth.common.garment_document import FreeCADDocumentObjectProtocol


class SimulationDocument(Protocol):
    """FreeCAD document operations required by simulation commands."""

    @property
    def Name(self) -> str:
        """Return the immutable internal document name."""
        ...

    @property
    def Objects(self) -> Sequence[FreeCADDocumentObjectProtocol]:
        """Return the document's native objects as a read-only sequence."""
        ...

    def addObject(self, object_type: str, name: str, /) -> FreeCADDocumentObjectProtocol:
        """Create a feature in the document."""
        ...

    def getObject(self, object_name: str, /) -> FreeCADDocumentObjectProtocol | None:
        """Find a feature by its stable internal name."""
        ...

    def recompute(self) -> int | None:
        """Recompute the document and return its native status code."""
        ...


class SimulationPatternPiece(FreeCADDocumentObjectProtocol, Protocol):
    """Document-global pattern-piece identity consumed by simulation scenes."""

    PieceId: str
    PatternType: str


class SimulationScene(FreeCADDocumentObjectProtocol, Protocol):
    """Complete persisted simulation scene contract shared by all workbench adapters."""

    @property
    def Document(self) -> SimulationDocument:
        """Return the document that owns this persistent simulation scene."""
        ...

    Steps: int
    Iterations: int
    TimeStep: float
    StartHeight: float
    StitchSamples: int
    GravityX: float
    GravityY: float
    GravityZ: float
    ClothPieces: Sequence[SimulationPatternPiece]
    DrapePanels: Sequence[FreeCADDocumentObjectProtocol]
    DrapeTarget: FreeCADDocumentObjectProtocol | None
    PinMode: str | list[str]
    PinSelection: list[str]
    SeamSelection: list[str]
    SimulatedTime: float
    ParticleCount: int
    FiniteState: bool
    CollisionX: float
    CollisionY: float
    CollisionZ: float
    CollisionRadius: float

    QualityPreset: str
    ParticleDistance: float
    SolverIterations: int
    SolverSubsteps: int
    FabricDensity: float
    FabricThickness: float
    FabricStretch: float
    FabricShear: float
    FabricBend: float
    FabricFriction: float
    FabricColor: tuple[float, float, float]
    FabricSpecular: float
    FabricRoughness: float
    FabricTransparency: int
    AvatarSkinOffset: float

    MaterialPreset: str
    StretchCompliance: float
    BendCompliance: float
    ArealDensity: float

    Proxy: SimulationProxyProtocol

    def addProperty(self, type_name: str, name: str, group: str) -> Self:
        """Register one persistent FreeCAD property on the scene."""
        ...


class SimulationProxyProtocol(Protocol):
    """Lifecycle methods available on the simulation feature proxy."""

    def execute(self, obj: SimulationScene) -> None:
        """Recompute the persisted simulation state."""
        ...

    def reset(self, obj: SimulationScene) -> None:
        """Reset transient solver state without changing authored inputs."""
        ...
