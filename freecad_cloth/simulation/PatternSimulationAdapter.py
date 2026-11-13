# Copyright (C) 2026 FreeCAD Cloth contributors
"""Resolve native Sketcher pattern geometry into solver-neutral PatternIR.

Editable Sketcher geometry is the only accepted source for production
simulation. The adapter fails closed when authority or semantic edge provenance
is absent instead of rebuilding geometry from cached outline or size fields.
"""

from collections.abc import Mapping, Sequence
from typing import Literal, Protocol, runtime_checkable

from pydantic import SkipValidation
from pydantic.dataclasses import dataclass as pydantic_dataclass

from freecad_cloth.common.garment_document import FreeCADDocumentObjectProtocol
from freecad_cloth.pattern.PatternGeometry import LineSegment, ParametricPattern, PolylineSegment
from freecad_cloth.pattern.PatternIR import BoundaryIR, PatternIR, PieceIR, SeamIR
from freecad_cloth.pattern.PatternModel import PatternPiece, Seam
from freecad_cloth.pattern.SeamReference import (
    NATIVE_SIGNATURE_PREFIX,
    ChangedEdgeReference,
    MissingEdgeReference,
    capture_edge_reference,
)
from freecad_cloth.sewing.SeamGraph import SeamGraph

CURVE_SAMPLES = 64
DEFAULT_PLACEMENT_TRANSLATION = 0.0
DEFAULT_PLACEMENT_ANGLE = 0.0
DEFAULT_ROTATION_AXIS_X = 0.0
DEFAULT_ROTATION_AXIS_Y = 0.0
DEFAULT_ROTATION_AXIS_Z = 1.0


type _SignatureValue = str | int | float | bool | tuple["_SignatureValue", ...] | None


class _NativeVector(Protocol):
    """Coordinate fields exposed by a FreeCAD placement vector."""

    x: float
    y: float
    z: float


class _NativeRotation(Protocol):
    """Rotation fields used to construct a stable placement signature."""

    Angle: float
    Axis: _NativeVector


class _NativePlacement(Protocol):
    """Translation and rotation members exposed by FreeCAD placements."""

    Base: _NativeVector
    Rotation: _NativeRotation


@runtime_checkable
class _PatternPieceFeature(FreeCADDocumentObjectProtocol, Protocol):
    """Persistent PatternPiece fields consumed by the simulation adapter."""

    PieceId: str
    GeometryAuthority: str
    Sketch: FreeCADDocumentObjectProtocol | None
    SeamAllowance: float
    GrainlineAngle: float
    Placement: _NativePlacement | None


class _SeamFeature(FreeCADDocumentObjectProtocol, Protocol):
    """Persisted semantic seam identity and side-specific edge provenance."""

    SeamId: str
    EdgeAId: str
    EdgeBId: str
    EdgeASignature: str
    EdgeBSignature: str


class _PatternDocument(Protocol):
    """Minimal document interface required by simulation pattern resolution."""

    Objects: Sequence[FreeCADDocumentObjectProtocol]


@pydantic_dataclass(frozen=True)
class ResolvedSimulationPattern:
    """Resolved PatternIR plus the originating FreeCAD PatternPiece objects.

    Attributes:
        pattern: Validated solver-neutral geometry and canonical seam relationships.
        pieces: Original document features indexed by their persistent PieceId.
        signature: Immutable source geometry, placement, and seam signature.
    """

    pattern: PatternIR
    pieces: Mapping[str, SkipValidation[_PatternPieceFeature]]
    signature: tuple[_SignatureValue, ...]

    def piece(self, piece_id: str) -> PieceIR:
        """Return one pattern piece by its stable semantic identifier.

        Args:
            piece_id: Identifier assigned to the requested pattern piece.

        Returns:
            The resolved PatternIR piece with the requested identity.

        Raises:
            KeyError: If no pattern piece has the requested identifier.
        """
        return self.pattern.piece(piece_id)


def is_sketch_authoritative(piece: _PatternPieceFeature) -> bool:
    """Return whether a document feature declares native Sketcher authority.

    Args:
        piece: FreeCAD document feature representing a pattern piece.

    Returns:
        True when the feature declares Sketcher as its authoritative geometry source.
    """
    return str(getattr(piece, "GeometryAuthority", "")).strip() == "Sketcher"


def resolve_simulation_pattern(
    doc: _PatternDocument | None,
    pieces: Sequence[_PatternPieceFeature],
    curve_samples: int = CURVE_SAMPLES,
) -> ResolvedSimulationPattern:
    """Resolve document PatternPieces and canonical seams into one PatternIR.

    Args:
        doc: FreeCAD document supplying persisted pattern-piece and seam objects.
        pieces: Selected PatternPiece features whose native Sketcher geometry is resolved.
        curve_samples: Number of samples used to represent each native sketch curve.

    Returns:
        PatternIR, source-piece objects, and a deterministic geometry/placement signature.

    Raises:
        ValueError: If the sample count is invalid, piece IDs repeat, or a seam is invalid.
        MissingEdgeReference: If a selected piece lacks authoritative Sketcher geometry.
        ChangedEdgeReference: If a semantic seam no longer matches its stored edge provenance.
    """
    if curve_samples < 2:
        msg = "curve_samples must be at least 2"
        raise ValueError(msg)

    selected_pieces = tuple(pieces)
    piece_objects: dict[str, _PatternPieceFeature] = {}
    piece_irs: list[PieceIR] = []
    for piece in selected_pieces:
        piece_id = str(getattr(piece, "PieceId", "")).strip()
        if not piece_id:
            msg = "simulation PatternPiece is missing PieceId"
            raise ValueError(msg)
        if piece_id in piece_objects:
            msg = f"simulation PatternPieces contain duplicate PieceId: {piece_id}"
            raise ValueError(msg)
        piece_objects[piece_id] = piece
        piece_irs.append(_resolve_piece_ir(piece, curve_samples))

    seams: list[SeamIR] = []
    selected_ids = set(piece_objects)
    document_objects = doc.Objects if doc is not None else ()
    for seam_obj in document_objects:
        seam_id = str(getattr(seam_obj, "SeamId", "")).strip()
        if not seam_id:
            continue
        piece_a_id = str(getattr(seam_obj, "PieceA", "")).strip()
        piece_b_id = str(getattr(seam_obj, "PieceB", "")).strip()
        if piece_a_id not in selected_ids or piece_b_id not in selected_ids:
            continue
        status = str(getattr(seam_obj, "Status", "Valid"))
        if status != "Valid":
            msg = f"cannot simulate invalid seam {seam_id}: {status}"
            raise ValueError(msg)
        piece_a_ir = next(piece_ir for piece_ir in piece_irs if piece_ir.id == piece_a_id)
        piece_b_ir = next(piece_ir for piece_ir in piece_irs if piece_ir.id == piece_b_id)
        edge_a: str = _resolve_seam_edge(piece_objects[piece_a_id], seam_obj, "A", piece_a_ir)
        edge_b: str = _resolve_seam_edge(piece_objects[piece_b_id], seam_obj, "B", piece_b_ir)
        seam = Seam(
            piece_a=piece_a_id,
            edge_a=edge_a,
            piece_b=piece_b_id,
            edge_b=edge_b,
            id=seam_id,
            start_a=float(getattr(seam_obj, "StartA", 0.0)),
            end_a=float(getattr(seam_obj, "EndA", 1.0)),
            start_b=float(getattr(seam_obj, "StartB", 0.0)),
            end_b=float(getattr(seam_obj, "EndB", 1.0)),
            reversed_b=bool(getattr(seam_obj, "ReversedB", False)),
            alignment=str(getattr(seam_obj, "Alignment", "endpoints") or "endpoints"),
            stitch_group=str(getattr(seam_obj, "StitchGroup", "") or seam_id),
            kind=str(getattr(seam_obj, "Kind", "plain") or "plain"),
        )
        seam.validate()
        seams.append(SeamIR.from_seam(seam, edge_a=edge_a, edge_b=edge_b))

    pattern = PatternIR(tuple(piece_irs), tuple(seams))
    pattern.validate()
    signature: tuple[_SignatureValue, ...] = (
        tuple(
            (
                piece_id,
                "Sketcher",
                tuple(
                    (
                        boundary.id,
                        boundary.kind,
                        boundary.parameter_range,
                        tuple(boundary.samples),
                    )
                    for boundary in pattern.piece(piece_id).boundaries
                ),
                _placement_signature(piece_objects[piece_id]),
            )
            for piece_id in sorted(piece_objects)
        ),
        tuple(
            (
                seam.id,
                seam.piece_a,
                seam.edge_a,
                seam.start_a,
                seam.end_a,
                seam.piece_b,
                seam.edge_b,
                seam.start_b,
                seam.end_b,
                seam.reversed_b,
                seam.alignment,
                seam.stitch_group,
                seam.kind,
            )
            for seam in sorted(pattern.seams, key=lambda value: value.id)
        ),
    )
    return ResolvedSimulationPattern(pattern, piece_objects, signature)


def resolve_piece_ir(piece: _PatternPieceFeature, curve_samples: int = CURVE_SAMPLES) -> PieceIR:
    """Resolve one Sketcher-authoritative document PatternPiece.

    Args:
        piece: FreeCAD document feature whose Sketcher geometry is authoritative.
        curve_samples: Number of samples used to represent each native sketch curve.

    Returns:
        The validated solver-neutral piece with stable semantic boundary identifiers.

    Raises:
        ValueError: If curve_samples is smaller than two.
        MissingEdgeReference: If the feature does not contain authoritative Sketcher data.
    """
    if curve_samples < 2:
        msg = "curve_samples must be at least 2"
        raise ValueError(msg)
    return _resolve_piece_ir(piece, curve_samples)


def geometry_from_piece_ir(piece_ir: PieceIR) -> ParametricPattern:
    """Convert PatternIR boundaries into the existing ParametricPattern mesh input.

    Args:
        piece_ir: Validated pattern piece containing native curve samples and identities.

    Returns:
        Parametric mesh input preserving each boundary's semantic identifier and shape.
    """
    segments: list[LineSegment | PolylineSegment] = []
    for boundary in piece_ir.boundaries:
        points = tuple((float(sample[0]), float(sample[1])) for sample in boundary.samples)
        if boundary.kind == "line" and len(points) == 2:
            segments.append(LineSegment(str(boundary.id), points[0], points[1]))
        else:
            segments.append(PolylineSegment(str(boundary.id), points))
    return ParametricPattern(segments)


def _resolve_piece_ir(piece: _PatternPieceFeature, curve_samples: int) -> PieceIR:
    """Build one solver-neutral piece from a native authoritative sketch.

    Args:
        piece: FreeCAD document feature whose Sketcher geometry is authoritative.
        curve_samples: Number of samples used to represent each native sketch curve.

    Returns:
        Validated PatternIR piece carrying native boundary provenance.

    Raises:
        MissingEdgeReference: If the feature lacks Sketcher authority or a sketch object.
        ValueError: If native sketch geometry cannot be converted into valid boundaries.
    """
    if not is_sketch_authoritative(piece):
        msg = (
            f"pattern piece {getattr(piece, 'PieceId', '')} must declare "
            "Sketcher as its geometry authority"
        )
        raise MissingEdgeReference(msg)
    sketch = getattr(piece, "Sketch", None)
    if sketch is None:
        msg = f"Sketch-authoritative pattern piece {getattr(piece, 'PieceId', '')} has no Sketch"
        raise MissingEdgeReference(msg)

    model = _piece_model(piece)
    graph = SeamGraph()
    graph.add_piece(model)
    return PatternIR.from_sketches(
        graph,
        {model.id: sketch},
        curve_samples=curve_samples,
    ).piece(model.id)


def _piece_model(piece: _PatternPieceFeature) -> PatternPiece:
    """Build PatternIR metadata while native Sketcher geometry supplies boundaries.

    Args:
        piece: Native document feature whose label, identity, and metadata are read.

    Returns:
        Canonical PatternPiece metadata used to validate the sketch-derived IR.
    """
    piece_id = str(getattr(piece, "PieceId", ""))
    label = str(getattr(piece, "Label", "") or getattr(piece, "Name", "") or piece_id)
    return PatternPiece(
        label,
        [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
        seam_allowance=float(getattr(piece, "SeamAllowance", 0.0)),
        grainline_angle=float(getattr(piece, "GrainlineAngle", 0.0)),
        id=piece_id,
    )


def _resolve_seam_edge(
    piece: _PatternPieceFeature,
    seam_obj: _SeamFeature,
    prefix: Literal["A", "B"],
    piece_ir: PieceIR,
) -> str:
    """Verify one persisted seam side against current semantic boundary provenance.

    Args:
        piece: Sketcher-authoritative document feature owning the boundary.
        seam_obj: Persisted sewing relationship containing its edge identity/signature.
        prefix: Side marker selecting the A or B edge identity and signature fields.
        piece_ir: Current solver-neutral geometry of the owning piece.

    Returns:
        Stable semantic edge identity to store in the solver-neutral seam record.

    Raises:
        MissingEdgeReference: If the piece or referenced semantic edge is unavailable.
        ChangedEdgeReference: If the stored signature does not match current native geometry.
    """
    if not is_sketch_authoritative(piece) or getattr(piece, "Sketch", None) is None:
        msg = (
            f"seam {getattr(seam_obj, 'SeamId', '')} references a piece "
            "without native Sketcher geometry"
        )
        raise MissingEdgeReference(msg)

    id_attribute = "EdgeAId" if prefix == "A" else "EdgeBId"
    signature_attribute: Literal["EdgeASignature", "EdgeBSignature"] = (
        "EdgeASignature" if prefix == "A" else "EdgeBSignature"
    )
    semantic_id = str(getattr(seam_obj, id_attribute, "")).strip()
    if not semantic_id:
        msg = (
            f"Sketcher-authoritative seam {getattr(seam_obj, 'SeamId', '')} "
            f"is missing {id_attribute}"
        )
        raise MissingEdgeReference(msg)

    boundary = next(
        (value for value in piece_ir.boundaries if value.id == semantic_id),
        None,
    )
    if boundary is None:
        msg = (
            f"semantic edge reference {semantic_id} is missing from pattern piece "
            f"{getattr(piece, 'PieceId', '')}"
        )
        raise MissingEdgeReference(msg)
    _validate_edge_signature(piece, seam_obj, semantic_id, boundary, signature_attribute)
    return semantic_id


def _validate_edge_signature(
    piece: _PatternPieceFeature,
    seam_obj: _SeamFeature,
    edge_id: str,
    boundary: BoundaryIR,
    signature_attribute: Literal["EdgeASignature", "EdgeBSignature"],
) -> None:
    """Require the stored seam signature to match current native PatternIR provenance.

    Args:
        piece: Sketcher-authoritative PatternPiece that owns the edge.
        seam_obj: Persisted semantic seam object with the signature property.
        edge_id: Stable semantic identity found in the current PatternIR boundary.
        boundary: Current PatternIR boundary record resolved by semantic identity.
        signature_attribute: Name of the stored side-specific signature property.

    Raises:
        ChangedEdgeReference: If the stored native provenance is missing or changed.
    """
    stored = str(getattr(seam_obj, signature_attribute, "")).strip()
    if not stored.startswith(NATIVE_SIGNATURE_PREFIX):
        msg = (
            f"native Sketcher seam {getattr(seam_obj, 'SeamId', '')} lacks "
            f"authoritative geometry provenance for {edge_id}"
        )
        raise ChangedEdgeReference(msg)

    samples = boundary.samples
    if len(samples) < 2:
        msg = f"semantic edge reference {edge_id} has fewer than two current samples"
        raise ChangedEdgeReference(msg)
    points = (
        (float(samples[0][0]), float(samples[0][1])),
        (float(samples[-1][0]), float(samples[-1][1])),
    )
    provenance = (
        "PatternIR",
        "Sketcher",
        boundary.kind,
        tuple(float(value) for value in boundary.parameter_range),
        samples,
    )
    current = capture_edge_reference(
        str(getattr(piece, "PieceId", "")),
        edge_id,
        points,
        provenance,
    ).signature
    if current != stored:
        msg = f"semantic edge reference {edge_id} geometry/provenance changed"
        raise ChangedEdgeReference(msg)


def _numeric_attribute(
    value: _NativeVector | _NativeRotation | None, name: str, default: float
) -> float:
    """Read a numeric FreeCAD placement field without accepting malformed values.

    Args:
        value: Native placement component that may expose a numeric member.
        name: Attribute name to read from the component.
        default: Fallback used when the component or member is not numeric.

    Returns:
        The numeric attribute converted to float, or the supplied default.
    """
    candidate = getattr(value, name, default)
    if isinstance(candidate, (int, float)) and not isinstance(candidate, bool):
        return float(candidate)
    return default


def _placement_signature(piece: _PatternPieceFeature) -> tuple[float, ...]:
    """Return the native placement fields used by the simulation source signature.

    Args:
        piece: PatternPiece feature whose native Placement is included in the signature.

    Returns:
        Translation, rotation angle, and rotation-axis components in stable order.
    """
    placement = getattr(piece, "Placement", None)
    if placement is None:
        return ()
    base = getattr(placement, "Base", None)
    rotation = getattr(placement, "Rotation", None)
    axis = getattr(rotation, "Axis", None) if rotation is not None else None
    return (
        _numeric_attribute(base, "x", DEFAULT_PLACEMENT_TRANSLATION),
        _numeric_attribute(base, "y", DEFAULT_PLACEMENT_TRANSLATION),
        _numeric_attribute(base, "z", DEFAULT_PLACEMENT_TRANSLATION),
        _numeric_attribute(rotation, "Angle", DEFAULT_PLACEMENT_ANGLE),
        _numeric_attribute(axis, "x", DEFAULT_ROTATION_AXIS_X),
        _numeric_attribute(axis, "y", DEFAULT_ROTATION_AXIS_Y),
        _numeric_attribute(axis, "z", DEFAULT_ROTATION_AXIS_Z),
    )
