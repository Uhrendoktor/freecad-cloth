"""Solver-neutral representation of a FreeCAD Cloth garment.

The IR deliberately contains no FreeCAD or solver types. Adapters may feed it
from the native document layer, while solvers consume only this module's stable
piece/edge/seam contracts.
"""
from dataclasses import dataclass, field
from math import hypot
from typing import Mapping, Sequence, Tuple

from PatternGeometry import LineSegment, ParametricPattern
from PatternModel import PatternPiece
from SeamGraph import SeamGraph

Point3 = Tuple[float, float, float]


@dataclass(frozen=True)
class BoundaryIR:
    """Resolved boundary with stable identity and native curve kind.

    ``samples`` are deterministic solver-friendly points. ``kind`` and
    ``parameter_range`` preserve the native Sketcher curve class at the
    adapter boundary so downstream code does not reduce curves to lines.
    """

    id: str
    kind: str
    samples: Tuple[Point3, ...]
    parameter_range: Tuple[float, float] = (0.0, 1.0)

    def validate(self) -> None:
        if not self.id.strip():
            raise ValueError("boundary id must not be empty")
        if self.kind not in {"line", "arc", "bspline", "bezier", "curve"}:
            raise ValueError("unsupported boundary kind")
        if len(self.samples) < 2:
            raise ValueError("boundary needs at least two samples")
        start, end = self.parameter_range
        if not end > start:
            raise ValueError("boundary parameter range must have positive extent")

    @property
    def length(self) -> float:
        return sum(
            hypot(b[0] - a[0], b[1] - a[1])
            for a, b in zip(self.samples, self.samples[1:])
        )


@dataclass(frozen=True)
class PieceIR:
    """One garment panel in solver-neutral local coordinates."""

    id: str
    name: str
    boundaries: Tuple[BoundaryIR, ...]
    material: str = ""
    seam_allowance: float = 0.0

    def validate(self) -> None:
        if not self.id.strip():
            raise ValueError("piece id must not be empty")
        if not self.boundaries:
            raise ValueError("piece needs at least one boundary")
        ids = [boundary.id for boundary in self.boundaries]
        if len(ids) != len(set(ids)):
            raise ValueError("piece boundary IDs must be unique")
        for boundary in self.boundaries:
            boundary.validate()
        if self.seam_allowance < 0.0:
            raise ValueError("seam allowance cannot be negative")


@dataclass(frozen=True)
class SeamIR:
    """Sewing relationship after raw edge indices have been resolved."""

    id: str
    piece_a: str
    edge_a: str
    piece_b: str
    edge_b: str
    start_a: float = 0.0
    end_a: float = 1.0
    start_b: float = 0.0
    end_b: float = 1.0
    reversed_b: bool = False
    alignment: str = "endpoints"
    stitch_group: str = ""
    kind: str = "plain"

    def validate(self, pieces: Mapping[str, PieceIR]) -> None:
        if not self.id.strip():
            raise ValueError("seam id must not be empty")
        for piece_id, edge_id in ((self.piece_a, self.edge_a), (self.piece_b, self.edge_b)):
            if piece_id not in pieces:
                raise ValueError(f"seam references unknown pattern piece: {piece_id}")
            if edge_id not in {edge.id for edge in pieces[piece_id].boundaries}:
                raise ValueError(f"seam references unknown boundary: {piece_id}:{edge_id}")
        for value in (self.start_a, self.end_a, self.start_b, self.end_b):
            if not 0.0 <= value <= 1.0:
                raise ValueError("seam edge ranges must be normalized")
        if self.start_a >= self.end_a or self.start_b >= self.end_b:
            raise ValueError("seam ranges must have positive extent")
        if self.alignment not in {"endpoints", "uniform"}:
            raise ValueError("unsupported sewing alignment")


@dataclass(frozen=True)
class PatternIR:
    """Complete solver-neutral garment snapshot."""

    pieces: Tuple[PieceIR, ...]
    seams: Tuple[SeamIR, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        piece_map = {piece.id: piece for piece in self.pieces}
        if len(piece_map) != len(self.pieces):
            raise ValueError("pattern piece IDs must be unique")
        for piece in self.pieces:
            piece.validate()
        seam_ids = {seam.id for seam in self.seams}
        if len(seam_ids) != len(self.seams):
            raise ValueError("seam IDs must be unique")
        for seam in self.seams:
            seam.validate(piece_map)

    def piece(self, piece_id: str) -> PieceIR:
        for piece in self.pieces:
            if piece.id == piece_id:
                return piece
        raise KeyError(piece_id)

    def boundary(self, piece_id: str, edge_id: str) -> BoundaryIR:
        piece = self.piece(piece_id)
        for edge in piece.boundaries:
            if edge.id == edge_id:
                return edge
        raise KeyError(f"{piece_id}:{edge_id}")

    @classmethod
    def from_graph(
        cls,
        graph: SeamGraph,
        geometries: Mapping[str, ParametricPattern] | None = None,
        materials: Mapping[str, str] | None = None,
        curve_samples: int = 32,
    ) -> "PatternIR":
        """Resolve a sewing graph into immutable solver-facing data.

        Integer seam references are accepted only at this adapter boundary and
        are immediately converted to semantic boundary IDs. String refs must
        already identify a boundary.
        """
        graph.validate()
        geometries = geometries or {}
        materials = materials or {}
        pieces = []
        for piece in graph.pieces.values():
            geometry = geometries.get(piece.id) or _line_geometry(piece)
            boundaries = tuple(_boundary_ir(segment, curve_samples) for segment in geometry.segments)
            pieces.append(
                PieceIR(
                    id=piece.id,
                    name=piece.name,
                    boundaries=boundaries,
                    material=materials.get(piece.id, str(piece.metadata.get("material", ""))),
                    seam_allowance=float(piece.seam_allowance),
                )
            )
        return _with_seams(cls, graph, pieces)

    @classmethod
    def from_sketches(
        cls,
        graph: SeamGraph,
        sketches: Mapping[str, object],
        materials: Mapping[str, str] | None = None,
        curve_samples: int = 32,
    ) -> "PatternIR":
        """Resolve native Sketcher geometry into the solver-neutral IR.

        The method intentionally has no FreeCAD import. A
        ``Sketcher::SketchObject`` supplies ``Geometry`` and optional
        ``SemanticEdgeIds``; the conversion emits deterministic samples plus
        curve kind/parameter metadata, while the native object stays outside
        the solver layer.
        """
        if curve_samples < 2:
            raise ValueError("curve_samples must be at least 2")
        graph.validate()
        materials = materials or {}
        pieces = []
        for piece in graph.pieces.values():
            sketch = sketches.get(piece.id)
            if sketch is None:
                raise ValueError(f"missing Sketcher geometry for pattern piece: {piece.id}")
            boundaries = _sketch_boundaries(sketch, piece.id, curve_samples)
            pieces.append(
                PieceIR(
                    id=piece.id,
                    name=piece.name,
                    boundaries=boundaries,
                    material=materials.get(piece.id, str(piece.metadata.get("material", ""))),
                    seam_allowance=float(piece.seam_allowance),
                )
            )
        return _with_seams(cls, graph, pieces)


def _with_seams(cls, graph: SeamGraph, pieces: Sequence[PieceIR]) -> PatternIR:
    piece_tuple = tuple(pieces)
    piece_map = {piece.id: piece for piece in piece_tuple}
    seams = []
    for pair in graph.seams.values():
        seam = pair.seam
        edge_a = _resolve_edge(seam.edge_a, piece_map[seam.piece_a])
        edge_b = _resolve_edge(seam.edge_b, piece_map[seam.piece_b])
        seams.append(
            SeamIR(
                id=seam.id,
                piece_a=seam.piece_a,
                edge_a=edge_a,
                piece_b=seam.piece_b,
                edge_b=edge_b,
                start_a=seam.start_a,
                end_a=seam.end_a,
                start_b=seam.start_b,
                end_b=seam.end_b,
                reversed_b=seam.reversed_b,
                alignment=seam.alignment,
                stitch_group=seam.stitch_group or seam.id,
                kind=seam.kind,
            )
        )
    result = cls(piece_tuple, tuple(seams))
    result.validate()
    return result


def _line_geometry(piece: PatternPiece) -> ParametricPattern:
    """Build a compatibility geometry when no richer curve adapter is given."""
    segments = []
    for index, start in enumerate(piece.outline):
        end = piece.outline[(index + 1) % len(piece.outline)]
        segments.append(LineSegment(f"edge:{index}", start, end))
    return ParametricPattern(segments)


def _boundary_ir(segment, curve_samples: int) -> BoundaryIR:
    if isinstance(segment, LineSegment):
        samples = (tuple((*segment.start, 0.0)), tuple((*segment.end, 0.0)))
        return BoundaryIR(segment.id, "line", samples)
    samples = tuple(tuple((*point, 0.0)) for point in segment.polyline(curve_samples))
    return BoundaryIR(segment.id, "curve", samples)


def _sketch_boundaries(sketch, piece_id: str, curve_samples: int) -> Tuple[BoundaryIR, ...]:
    geometry = tuple(getattr(sketch, "Geometry", ()) or ())
    if len(geometry) < 3:
        raise ValueError(f"Sketcher pattern needs at least three boundary geometries: {piece_id}")

    semantic_ids = tuple(getattr(sketch, "SemanticEdgeIds", ()) or ())
    boundaries = []
    for index, native in enumerate(geometry):
        if _is_construction(sketch, index):
            continue
        edge_id = (
            str(semantic_ids[index])
            if index < len(semantic_ids) and str(semantic_ids[index]).strip()
            else f"{piece_id}:edge:{index}"
        )
        boundaries.append(_native_boundary(native, edge_id, curve_samples))

    if len(boundaries) < 3:
        raise ValueError(f"Sketcher pattern needs at least three non-construction boundaries: {piece_id}")
    for index, current in enumerate(boundaries):
        following = boundaries[(index + 1) % len(boundaries)]
        if _distance3(current.samples[-1], following.samples[0]) > 1e-7:
            raise ValueError(f"Sketcher boundary is not closed between {current.id} and {following.id}")
    return tuple(boundaries)


def _is_construction(sketch, index: int) -> bool:
    getter = getattr(sketch, "getConstruction", None)
    if not callable(getter):
        return False
    try:
        return bool(getter(index))
    except (IndexError, TypeError):
        return False


def _native_boundary(native, edge_id: str, curve_samples: int) -> BoundaryIR:
    type_name = type(native).__name__.lower()
    if type_name == "linesegment":
        start = _point3(getattr(native, "StartPoint"))
        end = _point3(getattr(native, "EndPoint"))
        return BoundaryIR(edge_id, "line", (start, end))

    kind = {
        "arcofcircle": "arc",
        "bsplinecurve": "bspline",
        "beziercurve": "bezier",
    }.get(type_name)
    if kind is None:
        raise ValueError(f"unsupported Sketcher boundary geometry: {type(native).__name__}")

    first = _native_parameter(native, "FirstParameter", 0.0)
    last = _native_parameter(native, "LastParameter", 1.0)
    if last <= first:
        raise ValueError(f"invalid parameter range for Sketcher boundary: {edge_id}")
    samples = tuple(
        _point3(_native_value(native, first + (last - first) * i / (curve_samples - 1)))
        for i in range(curve_samples)
    )
    return BoundaryIR(edge_id, kind, samples, (first, last))


def _native_parameter(native, name: str, default: float) -> float:
    value = getattr(native, name, default)
    return float(value() if callable(value) else value)


def _native_value(native, parameter: float):
    value_at = getattr(native, "valueAt", None)
    if callable(value_at):
        return value_at(parameter)
    value = getattr(native, "value", None)
    if callable(value):
        return value(parameter)
    raise ValueError(f"Sketcher curve does not expose valueAt/value: {type(native).__name__}")


def _point3(point) -> Point3:
    return (float(point.x), float(point.y), float(getattr(point, "z", 0.0)))


def _distance3(a: Point3, b: Point3) -> float:
    return hypot(a[0] - b[0], a[1] - b[1]) + abs(a[2] - b[2])


def _resolve_edge(reference, piece: PieceIR) -> str:
    if isinstance(reference, bool):
        raise ValueError("boolean edge references are invalid")
    if isinstance(reference, int):
        if reference < 0 or reference >= len(piece.boundaries):
            raise ValueError(f"edge index is outside piece boundary: {piece.id}:{reference}")
        return piece.boundaries[reference].id
    if isinstance(reference, str) and reference in {edge.id for edge in piece.boundaries}:
        return reference
    raise ValueError(f"unresolvable seam edge reference: {piece.id}:{reference}")
