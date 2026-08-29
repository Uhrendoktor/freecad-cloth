"""Solver-neutral representation of a FreeCAD Cloth garment.

The IR deliberately contains no FreeCAD or solver types. Adapters may feed it
from the native document layer, while solvers consume only this module's stable
piece/edge/seam contracts.
"""
from dataclasses import dataclass, field, replace
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
    return _order_sketch_boundary(boundaries, piece_id)


def _order_sketch_boundary(boundaries: Sequence[BoundaryIR], piece_id: str) -> Tuple[BoundaryIR, ...]:
    """Resolve a closed Sketcher boundary from endpoint connectivity.

    Sketcher geometry insertion order is not a topological contract. Every
    endpoint must therefore belong to exactly two distinct boundary edges;
    after that invariant is established, the cycle is traversed from the
    lexicographically smallest semantic ID with a deterministic direction.
    """
    if len({boundary.id for boundary in boundaries}) != len(boundaries):
        raise ValueError(f"Sketcher boundary has duplicate semantic IDs: {piece_id}")

    vertices = []
    edge_vertices = []
    for edge_index, boundary in enumerate(boundaries):
        start = boundary.samples[0]
        end = boundary.samples[-1]
        if _distance3(start, end) <= 1e-7:
            raise ValueError(f"Sketcher boundary has a zero-length/self-loop edge: {boundary.id}")
        start_vertex = _find_vertex(vertices, start)
        end_vertex = _find_vertex(vertices, end)
        if start_vertex is None:
            start_vertex = len(vertices)
            vertices.append([start, []])
        if end_vertex is None:
            end_vertex = len(vertices)
            vertices.append([end, []])
        vertices[start_vertex][1].append(edge_index)
        vertices[end_vertex][1].append(edge_index)
        edge_vertices.append((start_vertex, end_vertex))

    for vertex_index, (_, incident) in enumerate(vertices):
        unique_incident = sorted(set(incident))
        if len(unique_incident) != 2:
            if len(unique_incident) < 2:
                raise ValueError(
                    f"Sketcher boundary is open at endpoint {vertex_index}: "
                    f"expected two connected edges, found {len(unique_incident)}"
                )
            raise ValueError(
                f"Sketcher boundary is ambiguous at endpoint {vertex_index}: "
                f"expected two connected edges, found {len(unique_incident)}"
            )

    adjacency = {index: set() for index in range(len(boundaries))}
    for incident in (set(vertex[1]) for vertex in vertices):
        first, second = tuple(incident)
        adjacency[first].add(second)
        adjacency[second].add(first)

    start_index = min(range(len(boundaries)), key=lambda index: (boundaries[index].id, index))
    start_a, start_b = edge_vertices[start_index]
    next_a = next(index for index in adjacency[start_index] if index != start_index)
    next_b = next(index for index in adjacency[start_index] if index != start_index)
    next_a = _next_edge_at_vertex(start_a, start_index, adjacency, edge_vertices)
    next_b = _next_edge_at_vertex(start_b, start_index, adjacency, edge_vertices)
    start_vertex, current_vertex = (
        (start_a, start_b)
        if (boundaries[next_a].id, _point_sort_key(vertices[start_a][0]))
        <= (boundaries[next_b].id, _point_sort_key(vertices[start_b][0]))
        else (start_b, start_a)
    )

    ordered = []
    visited = {start_index}
    ordered.append(_orient_boundary(boundaries[start_index], edge_vertices[start_index], start_vertex))
    current_edge = start_index

    while len(visited) < len(boundaries):
        candidates = [index for index in adjacency[current_edge] if index not in visited]
        if len(candidates) != 1:
            raise ValueError(
                f"Sketcher boundary is ambiguous while traversing from {boundaries[current_edge].id}"
            )
        next_edge = candidates[0]
        edge_start, edge_end = edge_vertices[next_edge]
        if edge_start == current_vertex:
            next_vertex = edge_end
            oriented = boundaries[next_edge]
        elif edge_end == current_vertex:
            next_vertex = edge_start
            oriented = replace(boundaries[next_edge], samples=tuple(reversed(boundaries[next_edge].samples)))
        else:
            raise ValueError(f"Sketcher boundary is disconnected near {boundaries[next_edge].id}")
        ordered.append(oriented)
        visited.add(next_edge)
        current_edge = next_edge
        current_vertex = next_vertex

    if start_vertex != current_vertex:
        raise ValueError(f"Sketcher boundary is open: traversal did not return to its start ({piece_id})")
    return tuple(ordered)


def _find_vertex(vertices, point):
    for index, (representative, _) in enumerate(vertices):
        if _distance3(representative, point) <= 1e-7:
            return index
    return None


def _next_edge_at_vertex(vertex_index, current_edge, adjacency, edge_vertices):
    candidates = [index for index in adjacency[current_edge] if index != current_edge]
    for index in candidates:
        start, end = edge_vertices[index]
        if start == vertex_index or end == vertex_index:
            return index
    raise ValueError("Sketcher boundary connectivity is inconsistent")


def _point_sort_key(point: Point3):
    return tuple(round(value, 12) for value in point)


def _orient_boundary(boundary, edge_vertices, start_vertex):
    edge_start, edge_end = edge_vertices
    if edge_start == start_vertex:
        return boundary
    if edge_end == start_vertex:
        return replace(boundary, samples=tuple(reversed(boundary.samples)))
    raise ValueError(f"Sketcher boundary orientation cannot start at {boundary.id}")


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
