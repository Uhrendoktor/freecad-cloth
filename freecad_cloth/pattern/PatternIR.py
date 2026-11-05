# Copyright (C) 2026 FreeCAD Cloth contributors
"""Solver-neutral representation of a FreeCAD Cloth garment.

The IR deliberately contains no FreeCAD or solver types. Adapters may feed it
from the native document layer, while solvers consume only this module's stable
piece/edge/seam contracts.
"""

from collections.abc import Mapping, Sequence
from dataclasses import field, replace
from math import hypot

from pydantic.dataclasses import dataclass as pydantic_dataclass

from freecad_cloth.common.ValidationModels import NormalizedRange, validate_finite_number
from freecad_cloth.pattern.PatternGeometry import LineSegment, ParametricPattern
from freecad_cloth.pattern.PatternModel import PatternPiece
from freecad_cloth.sewing.SeamGraph import SeamGraph

Point3 = tuple[float, float, float]


@pydantic_dataclass(frozen=True)
class BoundaryIR:
    """Resolved boundary with stable identity and native curve kind.

    ``samples`` are deterministic solver-friendly points. ``kind`` and
    ``parameter_range`` preserve the native Sketcher curve class at the
    adapter boundary so downstream code does not reduce curves to lines.
    """

    id: str
    kind: str
    samples: tuple[Point3, ...]
    parameter_range: tuple[float, float] = (0.0, 1.0)

    def validate(self) -> None:
        """Validate boundary identity, curve kind, sample count, and parameter range.

        Raises:
            ValueError: If the boundary ID or kind is invalid, fewer than two samples
                exist, or its source parameter interval has no positive extent.
        """
        if not self.id.strip():
            msg = "boundary id must not be empty"
            raise ValueError(msg)
        if self.kind not in {"line", "arc", "bspline", "bezier", "curve"}:
            msg = "unsupported boundary kind"
            raise ValueError(msg)
        if len(self.samples) < 2:
            msg = "boundary needs at least two samples"
            raise ValueError(msg)
        start, end = self.parameter_range
        if not end > start:
            msg = "boundary parameter range must have positive extent"
            raise ValueError(msg)

    @property
    def length(self) -> float:
        """Measure the boundary polyline in its local 2D coordinate plane.

        Returns:
            Sum of consecutive sample distances in pattern coordinate units.
        """
        return sum(
            hypot(b[0] - a[0], b[1] - a[1])
            for a, b in zip(self.samples, self.samples[1:], strict=False)
        )


@pydantic_dataclass(frozen=True)
class PieceIR:
    """One garment panel in solver-neutral local coordinates."""

    id: str
    name: str
    boundaries: tuple[BoundaryIR, ...]
    material: str = ""
    seam_allowance: float = 0.0

    def validate(self) -> None:
        """Validate piece identity, boundary membership, and seam-allowance value.

        Raises:
            ValueError: If the ID is empty, no boundaries exist, boundary IDs repeat,
                a child boundary is invalid, or seam allowance is negative.
        """
        if not self.id.strip():
            msg = "piece id must not be empty"
            raise ValueError(msg)
        if not self.boundaries:
            msg = "piece needs at least one boundary"
            raise ValueError(msg)
        ids = [boundary.id for boundary in self.boundaries]
        if len(ids) != len(set(ids)):
            msg = "piece boundary IDs must be unique"
            raise ValueError(msg)
        for boundary in self.boundaries:
            boundary.validate()
        if self.seam_allowance < 0.0:
            msg = "seam allowance cannot be negative"
            raise ValueError(msg)


@pydantic_dataclass(frozen=True)
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
        """Validate seam identity, piece/edge references, parameter ranges, and alignment.

        Args:
            pieces: Piece lookup used to resolve both semantic boundary references.

        Raises:
            ValueError: If either piece/edge reference is missing or the seam alignment
                is unsupported.
            ValidationError: If either normalized seam parameter range is invalid.
        """
        if not self.id.strip():
            msg = "seam id must not be empty"
            raise ValueError(msg)
        for piece_id, edge_id in ((self.piece_a, self.edge_a), (self.piece_b, self.edge_b)):
            if piece_id not in pieces:
                msg = f"seam references unknown pattern piece: {piece_id}"
                raise ValueError(msg)
            if edge_id not in {edge.id for edge in pieces[piece_id].boundaries}:
                msg = f"seam references unknown boundary: {piece_id}:{edge_id}"
                raise ValueError(msg)
        NormalizedRange(start=self.start_a, end=self.end_a)
        NormalizedRange(start=self.start_b, end=self.end_b)
        if self.alignment not in {"endpoints", "uniform"}:
            msg = "unsupported sewing alignment"
            raise ValueError(msg)


@pydantic_dataclass(frozen=True)
class PatternIR:
    """Complete solver-neutral garment snapshot."""

    pieces: tuple[PieceIR, ...]
    seams: tuple[SeamIR, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        """Validate unique piece/seam identities and all referenced child records.

        Raises:
            ValueError: If piece IDs or seam IDs repeat or any contained piece/seam
                violates its own validation contract.
        """
        piece_map = {piece.id: piece for piece in self.pieces}
        if len(piece_map) != len(self.pieces):
            msg = "pattern piece IDs must be unique"
            raise ValueError(msg)
        for piece in self.pieces:
            piece.validate()
        seam_ids = {seam.id for seam in self.seams}
        if len(seam_ids) != len(self.seams):
            msg = "seam IDs must be unique"
            raise ValueError(msg)
        for seam in self.seams:
            seam.validate(piece_map)

    def piece(self, piece_id: str) -> PieceIR:
        """Resolve one panel by its stable semantic identifier.

        Args:
            piece_id: Identifier assigned to the requested pattern piece.

        Returns:
            Matching solver-neutral panel record.

        Raises:
            KeyError: If no panel has the requested identifier.
        """
        for piece in self.pieces:
            if piece.id == piece_id:
                return piece
        raise KeyError(piece_id)

    def boundary(self, piece_id: str, edge_id: str) -> BoundaryIR:
        """Resolve one semantic edge within a specific panel.

        Args:
            piece_id: Identifier of the panel containing the boundary.
            edge_id: Stable boundary identifier within that panel.

        Returns:
            Matching solver-neutral boundary record.

        Raises:
            KeyError: If the piece or its requested boundary does not exist.
        """
        piece = self.piece(piece_id)
        for edge in piece.boundaries:
            if edge.id == edge_id:
                return edge
        msg = f"{piece_id}:{edge_id}"
        raise KeyError(msg)

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
        are immediately converted to semantic boundary IDs. String references must
        already identify a boundary.

        Args:
            graph: Validated sewing graph containing panels and seam relationships.
            geometries: Optional parametric geometry override for each piece ID.
            materials: Optional material name mapping keyed by piece ID.
            curve_samples: Sampling count used to preserve curved boundary shapes.

        Returns:
            Validated PatternIR containing panel boundaries and resolved semantic seams.
        """
        graph.validate()
        geometries = geometries or {}
        materials = materials or {}
        pieces = []
        for piece in graph.pieces.values():
            geometry = geometries.get(piece.id) or _line_geometry(piece)
            boundaries = tuple(
                _boundary_ir(segment, curve_samples) for segment in geometry.segments
            )
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
            msg = "curve_samples must be at least 2"
            raise ValueError(msg)
        graph.validate()
        materials = materials or {}
        pieces = []
        edge_index_maps = {}
        for piece in graph.pieces.values():
            sketch = sketches.get(piece.id)
            if sketch is None:
                msg = f"missing Sketcher geometry for pattern piece: {piece.id}"
                raise ValueError(msg)
            boundaries, edge_index_map = _sketch_boundaries(sketch, piece.id, curve_samples)
            edge_index_maps[piece.id] = edge_index_map
            pieces.append(
                PieceIR(
                    id=piece.id,
                    name=piece.name,
                    boundaries=boundaries,
                    material=materials.get(piece.id, str(piece.metadata.get("material", ""))),
                    seam_allowance=float(piece.seam_allowance),
                )
            )
        return _with_seams(cls, graph, pieces, edge_index_maps)


def _with_seams(
    cls,
    graph: SeamGraph,
    pieces: Sequence[PieceIR],
    edge_index_maps: Mapping[str, Mapping[int, str]] | None = None,
) -> PatternIR:
    """Resolve graph seam edges and build the final validated IR snapshot.

    Args:
        cls: PatternIR class or compatible constructor used for the result.
        graph: Source sewing graph supplying seam IDs and parameter ranges.
        pieces: Converted solver-neutral panel records.
        edge_index_maps: Optional native geometry-index to semantic-edge maps.

    Returns:
        Validated PatternIR containing converted panels and seams.
    """
    piece_tuple = tuple(pieces)
    piece_map = {piece.id: piece for piece in piece_tuple}
    edge_index_maps = edge_index_maps or {}
    seams = []
    for pair in graph.seams.values():
        seam = pair.seam
        edge_a = _resolve_edge(
            seam.edge_a, piece_map[seam.piece_a], edge_index_maps.get(seam.piece_a)
        )
        edge_b = _resolve_edge(
            seam.edge_b, piece_map[seam.piece_b], edge_index_maps.get(seam.piece_b)
        )
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
    """Build straight-edge compatibility geometry from an outline-only PatternPiece.

    Args:
        piece: Pattern panel whose polygon outline is used as the fallback geometry.

    Returns:
        Closed parametric boundary containing one stable line segment per outline edge.
    """
    segments = []
    for index, start in enumerate(piece.outline):
        end = piece.outline[(index + 1) % len(piece.outline)]
        segments.append(LineSegment(f"edge:{index}", start, end))
    return ParametricPattern(segments)


def _boundary_ir(segment, curve_samples: int) -> BoundaryIR:
    """Convert one parametric segment to a solver-neutral sampled boundary.

    Args:
        segment: Line, Bezier, or sampled polyline from the pattern geometry layer.
        curve_samples: Number of samples used when the segment is curved.

    Returns:
        Boundary record retaining segment ID, curve kind, and local XYZ samples.
    """
    if isinstance(segment, LineSegment):
        samples: tuple[Point3, ...] = (
            (segment.start[0], segment.start[1], 0.0),
            (segment.end[0], segment.end[1], 0.0),
        )
        return BoundaryIR(segment.id, "line", samples)
    samples = tuple((point[0], point[1], 0.0) for point in segment.polyline(curve_samples))
    return BoundaryIR(segment.id, "curve", samples)


def _sketch_boundaries(sketch, piece_id: str, curve_samples: int):
    """Extract non-construction Sketcher geometry with stable semantic edge IDs.

    Args:
        sketch: Native Sketcher-like object exposing Geometry and optional edge IDs.
        piece_id: Stable PatternPiece identifier used to generate fallback edge names.
        curve_samples: Number of samples generated for each curved native element.

    Returns:
        Ordered boundary tuple and a native geometry-index to semantic-ID mapping.

    Raises:
        ValueError: If no boundary geometry exists or a native element is unsupported.
    """
    geometry = tuple(getattr(sketch, "Geometry", ()) or ())
    if len(geometry) < 1:
        msg = f"Sketcher pattern needs at least one boundary geometry: {piece_id}"
        raise ValueError(msg)

    semantic_ids = tuple(getattr(sketch, "SemanticEdgeIds", ()) or ())
    boundaries = []
    edge_index_map = {}
    for index, native in enumerate(geometry):
        if _is_construction(sketch, index):
            continue
        edge_id = (
            str(semantic_ids[index])
            if index < len(semantic_ids) and str(semantic_ids[index]).strip()
            else f"{piece_id}:edge:{index}"
        )
        edge_index_map[index] = edge_id
        boundaries.append(_native_boundary(native, edge_id, curve_samples))

    if not boundaries:
        msg = f"Sketcher pattern has no non-construction boundary geometries: {piece_id}"
        raise ValueError(msg)
    return _order_sketch_boundary(boundaries, piece_id), edge_index_map


def _order_sketch_boundary(
    boundaries: Sequence[BoundaryIR], piece_id: str
) -> tuple[BoundaryIR, ...]:
    """Resolve a closed Sketcher boundary from endpoint connectivity.

    Sketcher geometry insertion order is not a topological contract. Every
    endpoint must therefore belong to exactly two distinct boundary edges;
    after that invariant is established, the cycle is traversed from the
    lexicographically smallest semantic ID with a deterministic direction.
    A single closed curve (for example a circle or closed B-spline) is already
    a complete boundary and does not need endpoint graph traversal.

    Args:
        boundaries: Sampled native edge records collected from one sketch.
        piece_id: Piece identifier included in boundary topology diagnostics.

    Returns:
        Boundary records ordered into one deterministic closed cycle.

    Raises:
        ValueError: If IDs repeat, endpoints are open or ambiguous, or edges are
            disconnected and cannot form one closed boundary loop.
    """
    if len({boundary.id for boundary in boundaries}) != len(boundaries):
        msg = f"Sketcher boundary has duplicate semantic IDs: {piece_id}"
        raise ValueError(msg)

    if len(boundaries) == 1:
        boundary = boundaries[0]
        if _distance3(boundary.samples[0], boundary.samples[-1]) <= 1e-7:
            return tuple(boundaries)
        msg = f"Sketcher boundary is open: the single boundary does not close ({piece_id})"
        raise ValueError(msg)

    vertices = []
    edge_vertices = []
    for edge_index, boundary in enumerate(boundaries):
        start = boundary.samples[0]
        end = boundary.samples[-1]
        if _distance3(start, end) <= 1e-7:
            msg = f"Sketcher boundary contains a closed curve alongside other boundary edges: {boundary.id}"
            raise ValueError(msg)
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
                msg = (
                    f"Sketcher boundary is open at endpoint {vertex_index}: "
                    f"expected two connected edges, found {len(unique_incident)}"
                )
                raise ValueError(msg)
            msg = (
                f"Sketcher boundary is ambiguous at endpoint {vertex_index}: "
                f"expected two connected edges, found {len(unique_incident)}"
            )
            raise ValueError(msg)

    adjacency = {index: set() for index in range(len(boundaries))}
    for incident in (set(vertex[1]) for vertex in vertices):
        first, second = tuple(incident)
        adjacency[first].add(second)
        adjacency[second].add(first)

    start_index = min(range(len(boundaries)), key=lambda index: (boundaries[index].id, index))
    start_a, start_b = edge_vertices[start_index]
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
    ordered.append(
        _orient_boundary(boundaries[start_index], edge_vertices[start_index], start_vertex)
    )
    current_edge = start_index

    while len(visited) < len(boundaries):
        candidates = [
            index
            for index in adjacency[current_edge]
            if index not in visited and current_vertex in edge_vertices[index]
        ]
        if not candidates:
            msg = (
                f"Sketcher boundary is disconnected near {boundaries[current_edge].id}: "
                "traversal cannot reach remaining edges"
            )
            raise ValueError(msg)
        if len(candidates) != 1:
            msg = f"Sketcher boundary is ambiguous while traversing from {boundaries[current_edge].id}"
            raise ValueError(msg)
        next_edge = candidates[0]
        edge_start, edge_end = edge_vertices[next_edge]
        if edge_start == current_vertex:
            next_vertex = edge_end
            oriented = boundaries[next_edge]
        elif edge_end == current_vertex:
            next_vertex = edge_start
            oriented = replace(
                boundaries[next_edge], samples=tuple(reversed(boundaries[next_edge].samples))
            )
        else:
            msg = f"Sketcher boundary is disconnected near {boundaries[next_edge].id}"
            raise ValueError(msg)
        ordered.append(oriented)
        visited.add(next_edge)
        current_edge = next_edge
        current_vertex = next_vertex

    if start_vertex != current_vertex:
        msg = f"Sketcher boundary is open: traversal did not return to its start ({piece_id})"
        raise ValueError(msg)
    return tuple(ordered)


def _find_vertex(vertices, point):
    """Find a previously registered endpoint within the topology merge tolerance.

    Args:
        vertices: Mutable representative-point and incident-edge entries.
        point: Candidate endpoint to locate.

    Returns:
        Existing vertex index when a representative is sufficiently close, or None.
    """
    for index, (representative, _) in enumerate(vertices):
        if _distance3(representative, point) <= 1e-7:
            return index
    return None


def _next_edge_at_vertex(vertex_index, current_edge, adjacency, edge_vertices):
    """Find the neighboring boundary edge incident to a connected endpoint.

    Args:
        vertex_index: Endpoint vertex at which the next edge must meet.
        current_edge: Current edge index whose adjacent edges are inspected.
        adjacency: Edge-to-neighboring-edge connectivity map.
        edge_vertices: Endpoint vertex indices for each boundary edge.

    Returns:
        Unique next edge index connected to the requested endpoint.

    Raises:
        ValueError: If no adjacent edge is incident to the endpoint.
    """
    candidates = [index for index in adjacency[current_edge] if index != current_edge]
    for index in candidates:
        start, end = edge_vertices[index]
        if start == vertex_index or end == vertex_index:
            return index
    msg = "Sketcher boundary connectivity is inconsistent"
    raise ValueError(msg)


def _point_sort_key(point: Point3) -> tuple[float, float, float]:
    """Round a point into a deterministic coordinate ordering key.

    Args:
        point: Three-dimensional endpoint coordinate.

    Returns:
        Coordinate tuple rounded to twelve decimal places for stable sorting.
    """
    return tuple(round(value, 12) for value in point)


def _orient_boundary(boundary, edge_vertices, start_vertex):
    """Orient a boundary sample sequence so it begins at a selected graph vertex.

    Args:
        boundary: Sampled boundary record to orient without changing its identity.
        edge_vertices: Start and end vertex indices associated with that boundary.
        start_vertex: Graph vertex that should become the first endpoint.

    Returns:
        Original or reversed boundary record with the requested start orientation.

    Raises:
        ValueError: If the requested vertex is not an endpoint of the boundary.
    """
    edge_start, edge_end = edge_vertices
    if edge_start == start_vertex:
        return boundary
    if edge_end == start_vertex:
        return replace(boundary, samples=tuple(reversed(boundary.samples)))
    msg = f"Sketcher boundary orientation cannot start at {boundary.id}"
    raise ValueError(msg)


def _is_construction(sketch, index: int) -> bool:
    """Check whether a native sketch geometry element is construction-only.

    Args:
        sketch: Sketcher-like object exposing getConstruction(index).
        index: Native geometry index under inspection.

    Returns:
        Whether the sketch reports this element as construction geometry.
    """
    getter = getattr(sketch, "getConstruction", None)
    if not callable(getter):
        return False
    try:
        return bool(getter(index))
    except (IndexError, TypeError):
        return False


def _native_boundary(native, edge_id: str, curve_samples: int) -> BoundaryIR:
    """Sample one native Sketcher geometry object into a typed boundary record.

    Args:
        native: Native line or parametric curve exposing point/parameter methods.
        edge_id: Semantic boundary identifier assigned by the source piece/sketch.
        curve_samples: Number of points used to sample non-linear geometry.

    Returns:
        Boundary record with line/arc/spline kind and native parameter interval.

    Raises:
        ValueError: If the native element is unsupported or its parameter interval
            is invalid.
    """
    type_name = type(native).__name__.lower()
    if type_name == "linesegment":
        start = _point3(native.StartPoint)
        end = _point3(native.EndPoint)
        return BoundaryIR(edge_id, "line", (start, end))

    kind = {
        "arcofcircle": "arc",
        "bsplinecurve": "bspline",
        "beziercurve": "bezier",
        "circle": "curve",
        "ellipse": "curve",
        "arcofellipse": "curve",
        "arcofhyperbola": "curve",
        "arcofparabola": "curve",
    }.get(type_name)
    if kind is None and callable(getattr(native, "valueAt", None)):
        kind = "curve"
    if kind is None:
        msg = f"unsupported Sketcher boundary geometry: {type(native).__name__}"
        raise ValueError(msg)

    first = _native_parameter(native, "FirstParameter", 0.0)
    last = _native_parameter(native, "LastParameter", 1.0)
    if last <= first:
        msg = f"invalid parameter range for Sketcher boundary: {edge_id}"
        raise ValueError(msg)
    samples = tuple(
        _point3(_native_value(native, first + (last - first) * i / (curve_samples - 1)))
        for i in range(curve_samples)
    )
    return BoundaryIR(edge_id, kind, samples, (first, last))


def _native_parameter(native, name: str, default: float) -> float:
    """Read a finite numeric native-curve parameter or use its fallback.

    Args:
        native: Sketcher geometry object containing the parameter attribute.
        name: Parameter attribute name, such as FirstParameter or LastParameter.
        default: Value used when the native object does not expose the attribute.

    Returns:
        Finite scalar value of the native parameter.
    """
    value = getattr(native, name, default)
    return validate_finite_number(value() if callable(value) else value)


def _native_value(native, parameter: float):
    """Evaluate one native curve through the host's supported value method.

    Args:
        native: Sketcher curve object exposing valueAt or value.
        parameter: Native curve parameter at which the coordinate is sampled.

    Returns:
        Native vector-like point returned by the curve evaluator.

    Raises:
        ValueError: If the native curve does not expose either supported evaluator.
    """
    value_at = getattr(native, "valueAt", None)
    if callable(value_at):
        return value_at(parameter)
    value = getattr(native, "value", None)
    if callable(value):
        return value(parameter)
    msg = f"Sketcher curve does not expose valueAt/value: {type(native).__name__}"
    raise ValueError(msg)


def _point3(point) -> Point3:
    """Convert a native vector-like sketch point into a plain XYZ tuple.

    Args:
        point: Native point exposing x/y and optional z components.

    Returns:
        Three floating-point coordinates, using zero for an absent Z component.
    """
    return (float(point.x), float(point.y), float(getattr(point, "z", 0.0)))


def _distance3(a: Point3, b: Point3) -> float:
    """Measure endpoint separation in the solver-neutral three-coordinate space.

    Args:
        a: First endpoint coordinate.
        b: Second endpoint coordinate.

    Returns:
        Sum of the planar Euclidean distance and absolute Z separation.
    """
    return hypot(a[0] - b[0], a[1] - b[1]) + abs(a[2] - b[2])


def _resolve_edge(
    reference, piece: PieceIR, edge_index_map: Mapping[int, str] | None = None
) -> str:
    """Resolve an integer or semantic seam edge reference to a stable boundary ID.

    Args:
        reference: Integer boundary index or existing semantic boundary identifier.
        piece: Solver-neutral piece whose boundaries provide the valid ID set.
        edge_index_map: Optional mapping for indices from the original Sketcher geometry.

    Returns:
        Stable semantic boundary ID for the selected edge.

    Raises:
        ValueError: If the reference is boolean, out of range, or does not resolve.
    """
    if isinstance(reference, bool):
        msg = "boolean edge references are invalid"
        raise ValueError(msg)
    if isinstance(reference, int):
        if edge_index_map is not None:
            if reference not in edge_index_map:
                msg = f"edge index is outside Sketcher boundary: {piece.id}:{reference}"
                raise ValueError(msg)
            return edge_index_map[reference]
        if reference < 0 or reference >= len(piece.boundaries):
            msg = f"edge index is outside piece boundary: {piece.id}:{reference}"
            raise ValueError(msg)
        return piece.boundaries[reference].id
    if isinstance(reference, str) and reference in {edge.id for edge in piece.boundaries}:
        return reference
    msg = f"unresolvable seam edge reference: {piece.id}:{reference}"
    raise ValueError(msg)
