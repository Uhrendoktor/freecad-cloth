# Copyright (C) 2026 FreeCAD Cloth contributors
"""Verify public simulation execution rebuilds after pattern source changes."""

from __future__ import annotations

from collections.abc import Sequence
from math import pi
from types import SimpleNamespace
from typing import TYPE_CHECKING, ClassVar

from freecad_cloth.common.garment_document import FreeCADDocumentObjectProtocol
from freecad_cloth.shared.SourceSignature import _SignatureValue
from freecad_cloth.simulation.PatternSimulationAdapter import resolve_simulation_pattern
from freecad_cloth.simulation.SimulationQualityRuntime import QualitySimulationProxy
from tests.support.assertions import require
from tests.support.pattern_edge_reference import edge_reference_signature as _edge_reference

if TYPE_CHECKING:
    from pytest import MonkeyPatch

DEFAULT_STITCH_SAMPLE_COUNT = 8
UPDATED_STITCH_SAMPLE_COUNT = 12
DEFAULT_PARTICLE_DISTANCE_MM = 4.0
DEFAULT_SOLVER_ITERATIONS = 8
DEFAULT_SOLVER_SUBSTEPS = 1
DEFAULT_FABRIC_DENSITY = 150.0
DEFAULT_FABRIC_THICKNESS_MM = 0.5
DEFAULT_FABRIC_STRETCH = 0.02
DEFAULT_FABRIC_SHEAR = 0.02
DEFAULT_FABRIC_BEND = 0.01
DEFAULT_FABRIC_FRICTION = 0.5
DEFAULT_FABRIC_COLOR = (0.72, 0.34, 0.46)
DEFAULT_FABRIC_SPECULAR = 0.25
DEFAULT_FABRIC_ROUGHNESS = 0.65
DEFAULT_AVATAR_SKIN_OFFSET_MM = 0.0
MOVED_X_MM = 25.0
MOVED_Y_MM = -10.0
MOVED_ANGLE_RADIANS = pi / 12.0
UPDATED_EDGE_LENGTH_MM = 12.0
EXPECTED_INITIAL_BUILD_COUNT = 1
EXPECTED_PATTERN_BUILD_COUNT = 3
SEAM_ID = "front-back"
FRONT_PIECE_ID = "front"
BACK_PIECE_ID = "back"
FRONT_EDGE_ID = "front:bottom"
BACK_EDGE_ID = "back:top"


class _Point:
    """Three-dimensional coordinate used by the native Sketcher fixture."""

    x: float
    y: float
    z: float

    def __init__(self, x: float, y: float, z: float = 0.0) -> None:
        """Store a point in the local pattern coordinate frame.

        Args:
            x: Coordinate along the local X axis.
            y: Coordinate along the local Y axis.
            z: Coordinate along the local Z axis.
        """
        self.x = x
        self.y = y
        self.z = z


class _LineSegment:
    """Native-like Sketcher line exposing start and end points."""

    StartPoint: _Point
    EndPoint: _Point

    def __init__(self, start: tuple[float, float], end: tuple[float, float]) -> None:
        """Create a line segment between two 2D points.

        Args:
            start: Local start coordinate.
            end: Local end coordinate.
        """
        self.StartPoint = _Point(*start)
        self.EndPoint = _Point(*end)


class _Sketch:
    """Sketch fixture with stable semantic edge identities."""

    Geometry: list[_LineSegment]
    SemanticEdgeIds: tuple[str, ...]

    def __init__(self, prefix: str) -> None:
        """Build a closed four-edge sketch with prefixed semantic IDs.

        Args:
            prefix: Stable piece identifier used in each boundary identity.
        """
        self.Geometry = [
            _LineSegment((0.0, 0.0), (10.0, 0.0)),
            _LineSegment((10.0, 0.0), (10.0, 10.0)),
            _LineSegment((10.0, 10.0), (0.0, 10.0)),
            _LineSegment((0.0, 10.0), (0.0, 0.0)),
        ]
        self.SemanticEdgeIds = (
            f"{prefix}:bottom",
            f"{prefix}:side",
            f"{prefix}:top",
            f"{prefix}:left",
        )
        self.getConstruction = _is_not_construction


def _is_not_construction(_index: int) -> bool:
    """Mark each fixture edge as real sketch geometry.

    Args:
        _index: Zero-based Sketcher geometry index.

    Returns:
        False because the fixture contains no construction geometry.
    """
    return False


class _Rotation:
    """Rotation fixture exposing the FreeCAD placement fields."""

    Angle: float
    Axis: _Point

    def __init__(self, angle: float = 0.0) -> None:
        """Create a rotation around the local Z axis.

        Args:
            angle: Rotation angle in radians.
        """
        self.Angle = angle
        self.Axis = _Point(0.0, 0.0, 1.0)


class _Placement:
    """Placement fixture combining translation and orientation."""

    Base: _Point
    Rotation: _Rotation

    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
        angle: float = 0.0,
    ) -> None:
        """Create a placement from translation and rotation components.

        Args:
            x: Translation along the X axis.
            y: Translation along the Y axis.
            z: Translation along the Z axis.
            angle: Rotation around the Z axis in radians.
        """
        self.Base = _Point(x, y, z)
        self.Rotation = _Rotation(angle)


class _Piece:
    """Sketcher-authoritative pattern piece used by the simulation adapter."""

    PatternType: str = "PatternPiece"
    TypeId: str = "App::FeaturePython"
    PropertiesList: ClassVar[list[str]] = []
    GeometryAuthority: str = "Sketcher"
    PieceId: str
    Name: str
    Label: str
    Sketch: _Sketch
    Placement: _Placement
    SeamAllowance: float
    GrainlineAngle: float

    def __init__(self, piece_id: str) -> None:
        """Create one native Sketcher piece with a stable semantic identity.

        Args:
            piece_id: Persistent pattern-piece identifier.
        """
        self.PieceId = piece_id
        self.Name = piece_id
        self.Label = piece_id
        self.Sketch = _Sketch(piece_id)
        self.Placement = _Placement()
        self.SeamAllowance = 0.0
        self.GrainlineAngle = 0.0


class _Seam:
    """Persisted seam fixture joining semantic edges from two pattern pieces."""

    Name: str = SEAM_ID
    Label: str = SEAM_ID
    TypeId: str = "App::FeaturePython"
    PropertiesList: ClassVar[list[str]] = []
    SeamId: str
    PieceA: str
    PieceB: str
    EdgeAId: str
    EdgeBId: str
    EdgeASignature: str
    EdgeBSignature: str
    EdgeA: int = 0
    EdgeB: int = 0
    StartA: float = 0.0
    EndA: float = 1.0
    StartB: float = 0.0
    EndB: float = 1.0
    ReversedB: bool = False
    Alignment: str = "uniform"
    StitchGroup: str = "waist"
    Kind: str = "plain"
    Status: str = "Valid"

    def __init__(self, signature_a: str, signature_b: str) -> None:
        """Create a valid seam with native edge provenance.

        Args:
            signature_a: Current native provenance for the front piece edge.
            signature_b: Current native provenance for the back piece edge.
        """
        self.SeamId = SEAM_ID
        self.PieceA = FRONT_PIECE_ID
        self.PieceB = BACK_PIECE_ID
        self.EdgeAId = FRONT_EDGE_ID
        self.EdgeBId = BACK_EDGE_ID
        self.EdgeASignature = signature_a
        self.EdgeBSignature = signature_b


class _Document:
    """Document fixture containing the canonical pattern seams."""

    Objects: list[FreeCADDocumentObjectProtocol]

    def __init__(self, objects: Sequence[FreeCADDocumentObjectProtocol]) -> None:
        """Store the document objects in their authored order.

        Args:
            objects: Pattern and seam objects visible through the document API.
        """
        self.Objects = list(objects)


class _Scene:
    """Simulation scene fixture with complete persisted quality controls."""

    QualityPreset: str
    ParticleDistance: float
    SolverIterations: int
    SolverSubsteps: int
    PinMode: str
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
    ClothPieces: tuple[_Piece, ...]
    Document: _Document
    Steps: int
    StitchSamples: int
    PinSelection: tuple[str, ...]
    DrapeTarget: None

    def __init__(self, document: _Document, pieces: tuple[_Piece, ...]) -> None:
        """Create a stable scene state for public proxy execution.

        Args:
            document: Document containing the selected pattern pieces and seams.
            pieces: Pattern pieces whose source geometry drives the simulation.
        """
        self.QualityPreset = "Balanced"
        self.ParticleDistance = DEFAULT_PARTICLE_DISTANCE_MM
        self.SolverIterations = DEFAULT_SOLVER_ITERATIONS
        self.SolverSubsteps = DEFAULT_SOLVER_SUBSTEPS
        self.PinMode = "Automatic"
        self.FabricDensity = DEFAULT_FABRIC_DENSITY
        self.FabricThickness = DEFAULT_FABRIC_THICKNESS_MM
        self.FabricStretch = DEFAULT_FABRIC_STRETCH
        self.FabricShear = DEFAULT_FABRIC_SHEAR
        self.FabricBend = DEFAULT_FABRIC_BEND
        self.FabricFriction = DEFAULT_FABRIC_FRICTION
        self.FabricColor = DEFAULT_FABRIC_COLOR
        self.FabricSpecular = DEFAULT_FABRIC_SPECULAR
        self.FabricRoughness = DEFAULT_FABRIC_ROUGHNESS
        self.FabricTransparency = 0
        self.AvatarSkinOffset = DEFAULT_AVATAR_SKIN_OFFSET_MM
        self.ClothPieces = pieces
        self.Document = document
        self.Steps = 0
        self.StitchSamples = DEFAULT_STITCH_SAMPLE_COUNT
        self.PinSelection = ()
        self.DrapeTarget = None


class _RuntimeBase:
    """Lightweight runtime state whose rebuild requests are observable."""

    backend: SimpleNamespace | None = SimpleNamespace()
    source_signature: _SignatureValue | None = None
    last_steps: int = 0
    seam_stitch_pairs: dict[str, tuple[tuple[int, int], ...]]


def _execution_probe(
    monkeypatch: MonkeyPatch,
) -> tuple[QualitySimulationProxy, _RuntimeBase, list[_SignatureValue]]:
    """Create a proxy that records rebuilds requested by its public execute method.

    Args:
        monkeypatch: Fixture that replaces expensive solver operations with recorders.

    Returns:
        The proxy, its synthetic runtime base, and rebuilt source signatures.
    """
    proxy = QualitySimulationProxy()
    runtime = _RuntimeBase()
    runtime.seam_stitch_pairs = {}
    rebuilt_signatures: list[_SignatureValue] = []

    def get_runtime_base() -> _RuntimeBase:
        """Return the runtime base used by this isolated execution probe.

        Returns:
            The synthetic state consumed by the public simulation proxy.
        """
        return runtime

    def build_pattern_scene(
        _scene: _Scene,
        _pieces: Sequence[_Piece],
        signature: _SignatureValue,
    ) -> None:
        """Record a requested rebuild and retain its source signature.

        Args:
            _scene: Simulation scene passed by the public execute operation.
            _pieces: Authoritative pattern pieces selected for the scene.
            signature: Current source and quality inputs used to build the scene.
        """
        rebuilt_signatures.append(signature)
        runtime.source_signature = signature

    def synchronize_provenance(_base: _RuntimeBase) -> None:
        """Stand in for seam-stitch provenance synchronization.

        Args:
            _base: Runtime state whose solver stitch provenance would be synchronized.
        """

    def advance(_scene: _Scene, _base: _RuntimeBase, _count: int) -> None:
        """Avoid advancing a solver while validating source invalidation.

        Args:
            _scene: Simulation scene normally advanced by the solver.
            _base: Runtime state normally containing the simulation backend.
            _count: Number of solver steps requested by the public proxy.
        """

    def publish(_scene: _Scene, _base: _RuntimeBase) -> None:
        """Avoid publishing mesh state while validating source invalidation.

        Args:
            _scene: Simulation scene whose display meshes would be updated.
            _base: Runtime state containing the solved particle positions.
        """

    monkeypatch.setattr(proxy, "_base_or_restore", get_runtime_base)
    monkeypatch.setattr(proxy, "_build_pattern_scene", build_pattern_scene)
    monkeypatch.setattr(proxy, "_sync_seam_stitch_provenance", synchronize_provenance)
    monkeypatch.setattr(proxy, "_advance", advance)
    monkeypatch.setattr(proxy, "_publish_state", publish)
    return proxy, runtime, rebuilt_signatures


def test_execute_rebuilds_when_pattern_geometry_or_placement_changes(
    monkeypatch: MonkeyPatch,
) -> None:
    """Rebuild the public simulation scene after piece placement or sketch edits.

    Args:
        monkeypatch: Fixture that replaces solver construction and publication operations.
    """
    piece = _Piece(FRONT_PIECE_ID)
    scene = _Scene(_Document([]), (piece,))
    proxy, _runtime, rebuilt_signatures = _execution_probe(monkeypatch)

    proxy.execute(scene)
    require(
        condition=len(rebuilt_signatures) == EXPECTED_INITIAL_BUILD_COUNT,
        message="The first public execution must build the selected pattern scene.",
    )
    baseline = rebuilt_signatures[-1]

    piece.Placement = _Placement(
        x=MOVED_X_MM,
        y=MOVED_Y_MM,
        angle=MOVED_ANGLE_RADIANS,
    )
    proxy.execute(scene)
    moved = rebuilt_signatures[-1]
    require(
        condition=len(rebuilt_signatures) == EXPECTED_INITIAL_BUILD_COUNT + 1,
        message="Changing piece placement must rebuild the simulation scene.",
    )
    require(
        condition=moved != baseline,
        message="The placement change must alter the source signature.",
    )

    piece.Sketch.Geometry[0] = _LineSegment((0.0, 0.0), (UPDATED_EDGE_LENGTH_MM, 0.0))
    piece.Sketch.Geometry[1] = _LineSegment(
        (UPDATED_EDGE_LENGTH_MM, 0.0), (10.0, 10.0)
    )
    proxy.execute(scene)
    require(
        condition=len(rebuilt_signatures) == EXPECTED_PATTERN_BUILD_COUNT,
        message="Editing Sketcher geometry must rebuild the simulation scene.",
    )
    require(
        condition=rebuilt_signatures[-1] != moved,
        message="The Sketcher geometry edit must alter the source signature.",
    )
    proxy.execute(scene)
    require(
        condition=len(rebuilt_signatures) == EXPECTED_PATTERN_BUILD_COUNT,
        message="Unchanged pattern inputs must not trigger another scene rebuild.",
    )


def test_execute_rebuilds_when_seam_orientation_or_sampling_changes(
    monkeypatch: MonkeyPatch,
) -> None:
    """Rebuild the public simulation scene after seam orientation or sampling edits.

    Args:
        monkeypatch: Fixture that replaces solver construction and publication operations.
    """
    front = _Piece(FRONT_PIECE_ID)
    back = _Piece(BACK_PIECE_ID)
    document = _Document([])
    initial = resolve_simulation_pattern(document, (front, back))
    seam = _Seam(
        _edge_reference(FRONT_PIECE_ID, initial.pattern.boundary(FRONT_PIECE_ID, FRONT_EDGE_ID)),
        _edge_reference(BACK_PIECE_ID, initial.pattern.boundary(BACK_PIECE_ID, BACK_EDGE_ID)),
    )
    document.Objects.append(seam)
    scene = _Scene(document, (front, back))
    proxy, _runtime, rebuilt_signatures = _execution_probe(monkeypatch)

    proxy.execute(scene)
    initial_signature = rebuilt_signatures[-1]
    seam.ReversedB = True
    proxy.execute(scene)
    reversed_signature = rebuilt_signatures[-1]
    require(
        condition=reversed_signature != initial_signature,
        message="Reversing a seam side must rebuild the simulation source scene.",
    )
    scene.StitchSamples = UPDATED_STITCH_SAMPLE_COUNT
    proxy.execute(scene)
    require(
        condition=rebuilt_signatures[-1] != reversed_signature,
        message="Changing seam stitch sampling must rebuild the simulation source scene.",
    )
    require(
        condition=len(rebuilt_signatures) == EXPECTED_PATTERN_BUILD_COUNT,
        message="Each source change must trigger exactly one pattern-scene rebuild.",
    )
