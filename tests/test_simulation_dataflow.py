# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression tests for pattern and sewing invalidation signatures."""

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

import freecad_cloth.simulation.SimulationObjects as SimulationObjects
from tests.support.assertions import require

DEFAULT_STITCH_SAMPLE_COUNT = 8
UPDATED_STITCH_SAMPLE_COUNT = 12
_SIMULATION_SOURCE_SIGNATURE_NAME = "_simulation_source_signature"

_simulation_source_signature = cast(
    "Callable[[object, Sequence[object]], object]",
    getattr(SimulationObjects, _SIMULATION_SOURCE_SIGNATURE_NAME),
)


class _Vec:
    """Three-dimensional vector fixture used by native placement doubles."""

    x: float
    y: float
    z: float

    def __init__(self, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> None:
        """Store the three vector coordinates.

        Args:
            x: Vector coordinate along the model X axis.
            y: Vector coordinate along the model Y axis.
            z: Vector coordinate along the model Z axis.
        """
        self.x, self.y, self.z = x, y, z


class _Rotation:
    """Rotation fixture exposing the FreeCAD angle and axis fields."""

    Angle: float
    Axis: _Vec

    def __init__(self, angle: float = 0.0) -> None:
        """Create a rotation around the model Z axis.

        Args:
            angle: Rotation angle in radians, matching the FreeCAD placement field.
        """
        self.Angle = angle
        self.Axis = _Vec(0.0, 0.0, 1.0)


class _Placement:
    """Placement fixture combining translation and rotation state."""

    Base: _Vec
    Rotation: _Rotation

    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
        angle: float = 0.0,
    ) -> None:
        """Create a placement from translation and angular components.

        Args:
            x: Translation along the model X axis.
            y: Translation along the model Y axis.
            z: Translation along the model Z axis.
            angle: Rotation around the model Z axis in radians.
        """
        self.Base = _Vec(x, y, z)
        self.Rotation = _Rotation(angle)


class _Piece:
    """Pattern-piece fixture exposing geometry and placement signature inputs."""

    PatternType = "PatternPiece"
    Name: str
    PieceId: str
    SewingOutline: str
    DraftingBoundary: str
    Placement: _Placement

    def __init__(self, name: str, piece_id: str) -> None:
        """Create a rectangular pattern piece with stable identity.

        Args:
            name: Internal document name for the pattern piece.
            piece_id: Persistent semantic piece identifier.
        """
        self.Name = name
        self.PieceId = piece_id
        self.SewingOutline = "[(0, 0), (100, 0), (100, 60), (0, 60)]"
        self.DraftingBoundary = self.SewingOutline
        self.Placement = _Placement()


class _Seam:
    """Sewing seam fixture exposing orientation and parameter signature inputs."""

    SeamId: str = "seam-1"
    PieceA: str = "piece-a"
    EdgeA: int = 0
    StartA: float = 0.0
    EndA: float = 1.0
    PieceB: str = "piece-b"
    EdgeB: int = 0
    StartB: float = 0.0
    EndB: float = 1.0
    ReversedB: bool = False


class _Document:
    """Minimal document double that retains the scene's authored seam records."""

    Objects: list[_Seam]

    def __init__(self, objects: list[_Seam]) -> None:
        """Store the ordered seam objects exposed through the document API.

        Args:
            objects: Seam records owned by the test simulation scene.
        """
        self.Objects = objects


class _Scene:
    """Simulation-scene fixture exposing its document and stitch sampling control."""

    StitchSamples: int
    Document: _Document

    def __init__(self, objects: list[_Seam]) -> None:
        """Create a scene with the supplied seam records.

        Args:
            objects: Ordered seam records available through the scene document.
        """
        self.Document = _Document(objects)
        self.StitchSamples = DEFAULT_STITCH_SAMPLE_COUNT


def test_signature_changes_for_piece_geometry_and_placement() -> None:
    """Change the source signature when piece placement or sewing geometry changes."""
    piece = _Piece("A", "piece-a")
    scene = _Scene([])
    baseline = _simulation_source_signature(scene, [piece])

    piece.Placement = _Placement(x=25.0, y=-10.0, angle=15.0)
    require(
        condition=_simulation_source_signature(scene, [piece]) != baseline,
        message="Moving a pattern piece must invalidate its source signature.",
    )

    moved = _simulation_source_signature(scene, [piece])
    piece.SewingOutline = "[(0, 0), (120, 0), (100, 60), (0, 60)]"
    require(
        condition=_simulation_source_signature(scene, [piece]) != moved,
        message="Changing the sewing outline must invalidate its source signature.",
    )


def test_signature_changes_for_seam_orientation_and_sampling() -> None:
    """Change the source signature when seam orientation or stitch sampling changes."""
    piece_a = _Piece("A", "piece-a")
    piece_b = _Piece("B", "piece-b")
    scene = _Scene([_Seam()])
    baseline = _simulation_source_signature(scene, [piece_a, piece_b])

    scene.Document.Objects[0].ReversedB = True
    require(
        condition=_simulation_source_signature(scene, [piece_a, piece_b]) != baseline,
        message="Reversing a seam side must invalidate the source signature.",
    )

    reversed_signature = _simulation_source_signature(scene, [piece_a, piece_b])
    scene.StitchSamples = UPDATED_STITCH_SAMPLE_COUNT
    require(
        condition=(_simulation_source_signature(scene, [piece_a, piece_b]) != reversed_signature),
        message="Changing stitch sampling must invalidate the source signature.",
    )
