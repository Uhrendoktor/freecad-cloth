"""Solver-neutral representation of a FreeCAD Cloth garment.

The IR deliberately contains no FreeCAD or solver types. Adapters may feed it
from the native document layer, while solvers consume only this module's stable
piece/edge/seam contracts.
"""
from dataclasses import dataclass, field
from math import hypot
from typing import Mapping, Tuple

from PatternGeometry import LineSegment, ParametricPattern, QuadraticBezier
from PatternModel import PatternPiece
from SeamGraph import SeamGraph

Point3 = Tuple[float, float, float]


@dataclass(frozen=True)
class BoundaryIR:
    """A resolved boundary with semantic identity and curve provenance.

    ``samples`` is a derived representation for consumers that need points.
    ``control_points`` and ``curve_type`` preserve the source curve contract so
    sampling never becomes the authoritative geometry. Native adapters can
    add richer curve types (arc, BSpline, Bezier, ...) without changing seam
    references or downstream solver APIs.
    """

    id: str
    kind: str
    samples: Tuple[Point3, ...]
    curve_type: str = "line"
    control_points: Tuple[Point3, ...] = ()

    def validate(self) -> None:
        if not self.id.strip():
            raise ValueError("boundary id must not be empty")
        if self.kind not in {"line", "curve"}:
            raise ValueError("unsupported boundary kind")
        if len(self.samples) < 2:
            raise ValueError("boundary needs at least two samples")
        if not self.curve_type.strip():
            raise ValueError("curve type must not be empty")
        if self.kind == "line" and self.curve_type != "line":
            raise ValueError("line boundary must use line curve type")
        if self.kind == "curve" and self.curve_type == "line":
            raise ValueError("curve boundary needs a non-line curve type")
        if self.control_points and len(self.control_points) < 2:
            raise ValueError("curve control points need at least two points")

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
        already identify a boundary. Thus downstream code never needs to
        interpret fragile ``EdgeN`` topology numbers.

        Piece and seam ordering is normalized by semantic ID so equivalent
        graphs produce byte-for-byte-equivalent tuple ordering regardless of
        dictionary insertion order.
        """
        graph.validate()
        geometries = geometries or {}
        materials = materials or {}
        pieces = []
        for piece in sorted(graph.pieces.values(), key=lambda value: value.id):
            geometry = geometries.get(piece.id)
            if geometry is None:
                geometry = _line_geometry(piece)
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
        piece_map = {piece.id: piece for piece in pieces}
        seams = []
        for pair in sorted(graph.seams.values(), key=lambda value: value.seam.id):
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
        result = cls(tuple(pieces), tuple(seams))
        result.validate()
        return result


def _line_geometry(piece: PatternPiece) -> ParametricPattern:
    """Build a compatibility geometry when no richer curve adapter is given."""
    segments = []
    for index, start in enumerate(piece.outline):
        end = piece.outline[(index + 1) % len(piece.outline)]
        segments.append(LineSegment(f"edge:{index}", start, end))
    return ParametricPattern(segments)


def _point3(point) -> Point3:
    return (float(point[0]), float(point[1]), 0.0)


def _boundary_ir(segment, curve_samples: int) -> BoundaryIR:
    if isinstance(segment, LineSegment):
        return BoundaryIR(
            segment.id,
            "line",
            (_point3(segment.start), _point3(segment.end)),
            curve_type="line",
            control_points=(_point3(segment.start), _point3(segment.end)),
        )
    if isinstance(segment, QuadraticBezier):
        samples = tuple(_point3(point) for point in segment.polyline(curve_samples))
        return BoundaryIR(
            segment.id,
            "curve",
            samples,
            curve_type="quadratic_bezier",
            control_points=(
                _point3(segment.start),
                _point3(segment.control),
                _point3(segment.end),
            ),
        )
    raise ValueError(f"unsupported boundary segment type: {type(segment).__name__}")


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
