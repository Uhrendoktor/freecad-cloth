"""Public, read-only production export adapter for native Cloth Pattern pieces.

FreeCAD/Sketcher objects remain authoritative. This module resolves a selected
PatternPiece into the existing deterministic SVG/DXF exporter without writing
back to the document.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from pathlib import Path
from typing import Iterable

from freecad_cloth.pattern.PatternDerivedGeometry import (
    DerivedPattern,
    Notch,
    PatternMark,
    add_marks,
    add_notches,
    derive_cut_boundary,
)
from freecad_cloth.pattern.PatternExport import to_dxf, to_svg, validate_export
from freecad_cloth.pattern.PatternGeometry import ParametricPattern
from freecad_cloth.pattern.PatternIR import PatternIR
from freecad_cloth.pattern.PatternModel import PatternPiece
from freecad_cloth.pattern.PatternTopologyRepair import seam_reference_status
from freecad_cloth.sewing.SeamGraph import SeamGraph


class PatternExportValidationError(ValueError):
    """Source data is not safe for production export."""


@dataclass(frozen=True)
class PatternExportSource:
    """Immutable export snapshot derived from document state."""

    pattern: ParametricPattern
    derived: DerivedPattern
    piece_id: str
    seam_ids: tuple[str, ...]
    units: str
    scale: float
    seam_allowance: float
    sketch_name: str

    @property
    def metadata(self) -> dict:
        """Return the deterministic semantic metadata embedded in exports."""
        return {
            "piece_id": self.piece_id,
            "seam_ids": list(self.seam_ids),
            "units": self.units,
            "scale": float(self.scale),
            "seam_allowance": float(self.seam_allowance),
            "edge_ids": [segment.id for segment in self.pattern.segments],
            "notch_ids": [notch.id for notch in self.derived.notches],
            "mark_ids": [mark.id for mark in self.derived.marks],
        }


class _SampledSegment:
    """A deterministic sampled native Sketch boundary edge."""

    def __init__(self, segment_id: str, points: Iterable[tuple[float, float]]):
        values = tuple((float(x), float(y)) for x, y in points)
        if len(values) < 2:
            raise ValueError(
                "native pattern edge has fewer than two samples: " + str(segment_id)
            )
        self.id = str(segment_id)
        self._points = values
        self.start = values[0]
        self.end = values[-1]

    def _lengths(self):
        lengths = [0.0]
        for a, b in zip(self._points, self._points[1:]):
            lengths.append(lengths[-1] + hypot(b[0] - a[0], b[1] - a[1]))
        return lengths

    def point(self, t: float):
        values = self.polyline(max(2, len(self._points)))
        t = min(1.0, max(0.0, float(t)))
        lengths = self._lengths()
        total = lengths[-1]
        if total <= 1e-12:
            return self.start
        target = total * t
        for index in range(1, len(values)):
            if target <= lengths[index]:
                span = lengths[index] - lengths[index - 1]
                local = 0.0 if span <= 1e-12 else (target - lengths[index - 1]) / span
                a, b = values[index - 1], values[index]
                return (
                    a[0] + (b[0] - a[0]) * local,
                    a[1] + (b[1] - a[1]) * local,
                )
        return values[-1]

    def polyline(self, samples: int = 32):
        samples = int(samples)
        if samples < 2:
            raise ValueError("samples must be at least 2")
        if len(self._points) == samples:
            return list(self._points)
        lengths = self._lengths()
        total = lengths[-1]
        if total <= 1e-12:
            return [self.start for _ in range(samples)]
        result = []
        for index in range(samples):
            target = total * index / float(samples - 1)
            for edge_index in range(1, len(self._points)):
                if target <= lengths[edge_index]:
                    span = lengths[edge_index] - lengths[edge_index - 1]
                    local = 0.0 if span <= 1e-12 else (target - lengths[edge_index - 1]) / span
                    a, b = self._points[edge_index - 1], self._points[edge_index]
                    result.append((
                        a[0] + (b[0] - a[0]) * local,
                        a[1] + (b[1] - a[1]) * local,
                    ))
                    break
            else:
                result.append(self._points[-1])
        return result


def _state_error(obj, role):
    state = tuple(str(value) for value in getattr(obj, "State", ()) or ())
    bad = {"Invalid", "Error", "Broken"}
    found = [value for value in state if value in bad]
    if found:
        return f"{role} has invalid FreeCAD state: {', '.join(found)}"
    return ""


def _build_pattern_from_piece(piece, sketch):
    piece_id = str(getattr(piece, "PieceId", "")).strip()
    seed = PatternPiece(
        str(getattr(piece, "Label", "PatternPiece")),
        [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
        seam_allowance=float(getattr(piece, "SeamAllowance", 0.0)),
        grainline_angle=float(getattr(piece, "GrainlineAngle", 0.0)),
        id=piece_id,
    )
    graph = SeamGraph()
    graph.add_piece(seed)
    piece_ir = PatternIR.from_sketches(graph, {piece_id: sketch}, curve_samples=64).piece(piece_id)
    segments = [
        _SampledSegment(
            boundary.id,
            [(sample[0], sample[1]) for sample in boundary.samples],
        )
        for boundary in piece_ir.boundaries
    ]
    return ParametricPattern(segments)


def _edge_alias(edge_id: str, edge_ids: tuple[str, ...]) -> str:
    raw = str(edge_id or "").strip()
    if not raw:
        return ""
    if raw in edge_ids:
        return raw
    if raw.startswith("edge:"):
        suffix = raw.split(":", 1)[1]
        if suffix.isdigit() and int(suffix) < len(edge_ids):
            return edge_ids[int(suffix)]
    cardinal = {"bottom": 0, "right": 1, "top": 2, "left": 3}
    if raw in cardinal and len(edge_ids) == 4:
        return edge_ids[cardinal[raw]]
    raise PatternExportValidationError(
        "pattern construction mark references unknown edge '" + raw + "'"
    )


def _document_marks(piece, pattern):
    doc = getattr(piece, "Document", None)
    if doc is None:
        raise PatternExportValidationError("pattern piece has no source FreeCAD document")
    edge_ids = tuple(segment.id for segment in pattern.segments)
    notches = []
    marks = []
    seen_ids = set()
    for obj in getattr(doc, "Objects", ()) or ():
        mark_type = str(getattr(obj, "PatternMarkType", "")).strip()
        if not mark_type or str(getattr(obj, "PieceId", "")) != str(piece.PieceId):
            continue
        mark_id = str(getattr(obj, "Name", "")).strip() or str(getattr(obj, "Label", "")).strip()
        if not mark_id:
            raise PatternExportValidationError(
                "pattern construction mark has no stable FreeCAD object id"
            )
        if mark_id in seen_ids:
            raise PatternExportValidationError(
                "duplicate construction mark id: " + mark_id
            )
        seen_ids.add(mark_id)
        segment = str(getattr(obj, "SegmentId", "") or "")
        segment_id = _edge_alias(segment, edge_ids) if segment else edge_ids[0]
        position = float(getattr(obj, "Position", 0.5))
        depth = float(getattr(obj, "Depth", 3.0))
        angle = float(
            getattr(obj, "Angle", getattr(piece, "GrainlineAngle", 0.0))
        )
        length = float(getattr(obj, "Length", 40.0))
        text = str(getattr(obj, "Text", "") or "")
        if mark_type == "Notch":
            notches.append(Notch(mark_id, segment_id, position, depth))
        else:
            marks.append(
                PatternMark(
                    mark_id,
                    mark_type,
                    segment_id,
                    position,
                    angle,
                    length,
                    text,
                )
            )

    grainline_angle = float(getattr(piece, "GrainlineAngle", 0.0))
    if grainline_angle and not any(mark.kind == "Grainline" for mark in marks):
        synthetic_id = str(piece.PieceId) + ":grainline"
        if synthetic_id not in seen_ids:
            marks.append(
                PatternMark(
                    synthetic_id,
                    "Grainline",
                    edge_ids[0],
                    0.5,
                    grainline_angle,
                    max(
                        10.0,
                        min(
                            float(getattr(piece, "Width", 10.0)),
                            float(getattr(piece, "Height", 10.0)),
                        ) * 0.6,
                    ),
                    "Grainline",
                )
            )
    return tuple(notches), tuple(marks)


def _referenced_seams(piece):
    doc = getattr(piece, "Document", None)
    piece_id = str(getattr(piece, "PieceId", ""))
    seams = []
    for seam in getattr(doc, "Objects", ()) or ():
        seam_id = str(getattr(seam, "SeamId", "")).strip()
        if not seam_id:
            continue
        if not (
            str(getattr(seam, "PieceA", "")) == piece_id
            or str(getattr(seam, "PieceB", "")) == piece_id
        ):
            continue
        for side in ("A", "B"):
            valid, reason = seam_reference_status(seam, side)
            if not valid:
                raise PatternExportValidationError(
                    "cannot export '" + piece_id + "': seam " + seam_id
                    + " side " + side + " is " + reason
                )
        status = str(getattr(seam, "Status", "Valid"))
        if status != "Valid":
            raise PatternExportValidationError(
                "cannot export '" + piece_id + "': seam " + seam_id
                + " is " + status
            )
        seams.append(seam_id)
    return tuple(sorted(set(seams)))


def build_export_source(piece, units="mm", scale=1.0):
    """Validate a PatternPiece and build an immutable production export source."""
    if piece is None or str(getattr(piece, "PatternType", "")) != "PatternPiece":
        raise PatternExportValidationError(
            "select a Cloth PatternPiece before exporting"
        )
    piece_id = str(getattr(piece, "PieceId", "")).strip()
    if not piece_id:
        raise PatternExportValidationError("selected PatternPiece has no stable piece ID")
    error = _state_error(piece, "pattern piece")
    if error:
        raise PatternExportValidationError(error)
    doc = getattr(piece, "Document", None)
    if doc is None:
        raise PatternExportValidationError(
            "selected PatternPiece is not attached to a FreeCAD document"
        )

    authority = str(getattr(piece, "GeometryAuthority", "")).strip()
    sketch = getattr(piece, "Sketch", None)
    if authority != "Sketcher" or sketch is None:
        raise PatternExportValidationError(
            "pattern geometry is not backed by an authoritative native Sketcher source; "
            "create/link a native Sketch before exporting"
        )
    if getattr(sketch, "Document", None) is not doc:
        raise PatternExportValidationError(
            "authoritative Sketch belongs to a different FreeCAD document"
        )
    error = _state_error(sketch, "authoritative Sketch")
    if error:
        raise PatternExportValidationError(error)
    if str(getattr(sketch, "PatternPieceId", "")) != piece_id:
        raise PatternExportValidationError(
            "authoritative Sketch is linked to a different piece ID"
        )
    geometry = tuple(getattr(sketch, "Geometry", ()) or ())
    if not geometry:
        raise PatternExportValidationError("authoritative Sketch contains no geometry")
    semantic_ids = tuple(
        str(value) for value in getattr(sketch, "SemanticEdgeIds", ()) or ()
    )
    nonempty_ids = [value for value in semantic_ids if value.strip()]
    if len(nonempty_ids) != len(set(nonempty_ids)):
        raise PatternExportValidationError(
            "authoritative Sketch has duplicate semantic edge IDs"
        )
    if len(nonempty_ids) < sum(
        1
        for index, _geometry in enumerate(geometry)
        if not bool(getattr(sketch, "getConstruction", lambda _i: False)(index))
    ):
        raise PatternExportValidationError(
            "authoritative Sketch has missing semantic edge IDs"
        )
    try:
        shape = sketch.Shape
        if shape.isNull() or not shape.isValid():
            raise PatternExportValidationError("authoritative Sketch shape is invalid")
    except AttributeError as exc:
        raise PatternExportValidationError(
            "authoritative Sketch cannot provide a valid FreeCAD shape"
        ) from exc

    units = str(units).strip()
    if units not in {"mm", "cm", "in"}:
        raise PatternExportValidationError(
            "export units must be one of: mm, cm, in"
        )
    try:
        scale = float(scale)
    except (TypeError, ValueError) as exc:
        raise PatternExportValidationError("export scale must be numeric") from exc
    if scale <= 0:
        raise PatternExportValidationError("export scale must be greater than zero")

    pattern = _build_pattern_from_piece(piece, sketch)
    notches, marks = _document_marks(piece, pattern)
    derived = derive_cut_boundary(
        pattern,
        float(getattr(piece, "SeamAllowance", 0.0)),
        curve_samples=64,
    )
    if notches:
        derived = add_notches(derived, notches)
    if marks:
        derived = add_marks(derived, marks)
    seam_ids = _referenced_seams(piece)
    return PatternExportSource(
        pattern=pattern,
        derived=derived,
        piece_id=piece_id,
        seam_ids=seam_ids,
        units=units,
        scale=scale,
        seam_allowance=float(getattr(piece, "SeamAllowance", 0.0)),
        sketch_name=str(getattr(sketch, "Name", "")),
    )


def export_pattern_piece(piece, svg_path, dxf_path, units="mm", scale=1.0):
    """Write deterministic SVG and DXF artifacts without mutating the source."""
    source = build_export_source(piece, units=units, scale=scale)
    output_scale = source.scale * {
        "mm": 1.0,
        "cm": 0.1,
        "in": 1.0 / 25.4,
    }[source.units]
    svg = to_svg(
        source.pattern,
        curve_samples=64,
        units=source.units,
        scale=output_scale,
        derived=source.derived,
        piece_id=source.piece_id,
        seam_ids=source.seam_ids,
        seam_allowance=source.seam_allowance,
        metadata_scale=source.scale,
    )
    dxf = to_dxf(
        source.pattern,
        curve_samples=64,
        units=source.units,
        scale=output_scale,
        derived=source.derived,
        piece_id=source.piece_id,
        seam_ids=source.seam_ids,
        seam_allowance=source.seam_allowance,
        metadata_scale=source.scale,
    )
    validate_export(
        source.pattern,
        svg,
        "svg",
        curve_samples=64,
        units=source.units,
        scale=output_scale,
        derived=source.derived,
        piece_id=source.piece_id,
        seam_ids=source.seam_ids,
        seam_allowance=source.seam_allowance,
        metadata_scale=source.scale,
    )
    validate_export(
        source.pattern,
        dxf,
        "dxf",
        curve_samples=64,
        units=source.units,
        scale=output_scale,
        derived=source.derived,
        piece_id=source.piece_id,
        seam_ids=source.seam_ids,
        seam_allowance=source.seam_allowance,
        metadata_scale=source.scale,
    )
    svg_path = Path(svg_path).expanduser()
    dxf_path = Path(dxf_path).expanduser()
    if svg_path.resolve() == dxf_path.resolve():
        raise PatternExportValidationError(
            "SVG and DXF output paths must be different"
        )
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    dxf_path.parent.mkdir(parents=True, exist_ok=True)
    svg_path.write_text(svg, encoding="utf-8", newline="\n")
    dxf_path.write_text(dxf, encoding="utf-8", newline="\n")
    return source
