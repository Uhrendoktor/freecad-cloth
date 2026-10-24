# Copyright (C) 2026 FreeCAD Cloth contributors
"""Resolve native Sketcher pattern geometry into solver-neutral PatternIR.

Editable Sketcher geometry is the only accepted source for production
simulation. The adapter fails closed when authority or semantic edge provenance
is absent instead of rebuilding geometry from cached outline or size fields.
"""

from collections.abc import Mapping, Sequence

from pydantic.dataclasses import dataclass as pydantic_dataclass

from freecad_cloth.pattern.PatternGeometry import LineSegment, ParametricPattern, PolylineSegment
from freecad_cloth.pattern.PatternIR import PatternIR, SeamIR
from freecad_cloth.pattern.PatternModel import PatternPiece, Seam
from freecad_cloth.pattern.SeamReference import (
    ChangedEdgeReference,
    MissingEdgeReference,
    capture_edge_reference,
)
from freecad_cloth.sewing.SeamGraph import SeamGraph

CURVE_SAMPLES = 64


@pydantic_dataclass(frozen=True)
class ResolvedSimulationPattern:
    """Resolved PatternIR plus the originating FreeCAD PatternPiece objects."""

    pattern: PatternIR
    pieces: Mapping[str, object]
    signature: tuple[object, ...]

    def piece(self, piece_id: str):
        """Provide the public piece operation."""
        return self.pattern.piece(piece_id)


def is_sketch_authoritative(piece) -> bool:
    """Return whether this document object declares native Sketcher authority."""
    return str(getattr(piece, "GeometryAuthority", "")).strip() == "Sketcher"


def resolve_simulation_pattern(doc, pieces: Sequence[object], curve_samples: int = CURVE_SAMPLES):
    """Resolve document PatternPieces and canonical seams into one PatternIR."""
    if curve_samples < 2:
        msg = "curve_samples must be at least 2"
        raise ValueError(msg)

    pieces = tuple(pieces)
    piece_objects = {}
    piece_irs = []
    for piece in pieces:
        piece_id = str(getattr(piece, "PieceId", "")).strip()
        if not piece_id:
            msg = "simulation PatternPiece is missing PieceId"
            raise ValueError(msg)
        if piece_id in piece_objects:
            msg = f"simulation PatternPieces contain duplicate PieceId: {piece_id}"
            raise ValueError(msg)
        piece_objects[piece_id] = piece
        piece_irs.append(_resolve_piece_ir(piece, curve_samples))

    seams = []
    selected = set(piece_objects)
    for seam_obj in getattr(doc, "Objects", ()):
        seam_id = str(getattr(seam_obj, "SeamId", "")).strip()
        if not seam_id:
            continue
        piece_a_id = str(getattr(seam_obj, "PieceA", "")).strip()
        piece_b_id = str(getattr(seam_obj, "PieceB", "")).strip()
        if piece_a_id not in selected or piece_b_id not in selected:
            continue
        status = str(getattr(seam_obj, "Status", "Valid"))
        if status != "Valid":
            msg = f"cannot simulate invalid seam {seam_id}: {status}"
            raise ValueError(msg)
        piece_a_ir = next(piece_ir for piece_ir in piece_irs if piece_ir.id == piece_a_id)
        piece_b_ir = next(piece_ir for piece_ir in piece_irs if piece_ir.id == piece_b_id)
        edge_a = _resolve_seam_edge(piece_objects[piece_a_id], seam_obj, "A", piece_a_ir)
        edge_b = _resolve_seam_edge(piece_objects[piece_b_id], seam_obj, "B", piece_b_ir)
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
        seams.append(
            SeamIR(
                id=seam.id,
                piece_a=seam.piece_a,
                edge_a=seam.edge_a,
                piece_b=seam.piece_b,
                edge_b=seam.edge_b,
                start_a=seam.start_a,
                end_a=seam.end_a,
                start_b=seam.start_b,
                end_b=seam.end_b,
                reversed_b=seam.reversed_b,
                alignment=seam.alignment,
                stitch_group=seam.stitch_group,
                kind=seam.kind,
            )
        )

    pattern = PatternIR(tuple(piece_irs), tuple(seams))
    pattern.validate()
    signature = (
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


def resolve_piece_ir(piece, curve_samples: int = CURVE_SAMPLES):
    """Resolve one Sketcher-authoritative document PatternPiece."""
    if curve_samples < 2:
        msg = "curve_samples must be at least 2"
        raise ValueError(msg)
    return _resolve_piece_ir(piece, curve_samples)


def geometry_from_piece_ir(piece_ir):
    """Convert PatternIR boundaries into the existing ParametricPattern mesh input."""
    segments = []
    for boundary in piece_ir.boundaries:
        points = tuple((float(sample[0]), float(sample[1])) for sample in boundary.samples)
        if boundary.kind == "line" and len(points) == 2:
            segments.append(LineSegment(str(boundary.id), points[0], points[1]))
        else:
            segments.append(PolylineSegment(str(boundary.id), points))
    return ParametricPattern(segments)


def _resolve_piece_ir(piece, curve_samples):
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


def _piece_model(piece):
    """Build PatternIR metadata; native Sketcher geometry supplies the boundary."""
    return PatternPiece(
        str(getattr(piece, "Label", "") or getattr(piece, "Name", "") or piece.PieceId),
        [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
        seam_allowance=float(getattr(piece, "SeamAllowance", 0.0)),
        grainline_angle=float(getattr(piece, "GrainlineAngle", 0.0)),
        id=str(piece.PieceId),
    )


def _resolve_seam_edge(piece, seam_obj, prefix, piece_ir):
    if not is_sketch_authoritative(piece) or getattr(piece, "Sketch", None) is None:
        msg = f"seam {getattr(seam_obj, 'SeamId', '')} references a piece without native Sketcher geometry"
        raise MissingEdgeReference(msg)

    id_attribute = "EdgeAId" if prefix == "A" else "EdgeBId"
    signature_attribute = "EdgeASignature" if prefix == "A" else "EdgeBSignature"
    semantic_id = str(getattr(seam_obj, id_attribute, "")).strip()
    if not semantic_id:
        msg = f"Sketcher-authoritative seam {getattr(seam_obj, 'SeamId', '')} is missing {id_attribute}"
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
    _validate_edge_signature(
        piece,
        seam_obj,
        semantic_id,
        boundary,
        signature_attribute,
        True,
    )
    return semantic_id


def _validate_edge_signature(piece, seam_obj, edge_id, boundary, signature_attribute, native):
    stored = str(getattr(seam_obj, signature_attribute, "")).strip()
    if native and not stored.startswith("native-v1:"):
        raise ChangedEdgeReference(
            "native Sketcher seam {} lacks authoritative geometry provenance for {}".format(
                getattr(seam_obj, "SeamId", ""), edge_id
            )
        )
    if not stored:
        return

    samples = tuple(tuple(point) for point in boundary.samples)
    points = (
        (samples[0][0], samples[0][1]),
        (samples[-1][0], samples[-1][1]),
    )
    provenance = None
    if native:
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


def _placement_signature(piece):
    placement = getattr(piece, "Placement", None)
    if placement is None:
        return ()
    base = getattr(placement, "Base", None)
    rotation = getattr(placement, "Rotation", None)
    axis = getattr(rotation, "Axis", None) if rotation is not None else None
    return (
        float(getattr(base, "x", 0.0)),
        float(getattr(base, "y", 0.0)),
        float(getattr(base, "z", 0.0)),
        float(getattr(rotation, "Angle", 0.0)) if rotation is not None else 0.0,
        float(getattr(axis, "x", 0.0)) if axis is not None else 0.0,
        float(getattr(axis, "y", 0.0)) if axis is not None else 0.0,
        float(getattr(axis, "z", 1.0)) if axis is not None else 1.0,
    )
