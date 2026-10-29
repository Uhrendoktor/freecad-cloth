# Copyright (C) 2026 FreeCAD Cloth contributors
"""Contract tests for Sketcher-authoritative sewing geometry."""

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from freecad_cloth.pattern.SeamReference import MissingEdgeReference
from freecad_cloth.sewing.SewingObjects import (
    SewingOperationProxy,
    _edge_length,
    _native_edge,
    _sample_polyline,
    _seam_correspondence,
    _seam_edge_index,
    _seam_length,
)
from freecad_cloth.simulation.SimulationObjects import _sample_boundary


class _PolylineEdge:
    """FreeCAD-like edge exposing ordered 2D samples."""

    def __init__(self, points: tuple[tuple[float, float], ...]) -> None:
        """Store native edge samples.

        Args:
            points: Coordinates ordered from the edge's first endpoint to its last.
        """
        self.points = points

    def discretize(self, number: int = 64) -> list[SimpleNamespace]:
        """Return the authored points in FreeCAD-vector form.

        Args:
            number: Requested sample count; the fixture keeps its authored samples.

        Returns:
            Objects exposing x, y and z coordinates.
        """
        return [SimpleNamespace(x=x, y=y, z=0.0) for x, y in self.points]


class _Geometry:
    """Sketch.Geometry item that returns a native shape edge."""

    def __init__(self, edge: _PolylineEdge) -> None:
        """Associate a native edge with one sketch geometry index.

        Args:
            edge: Edge represented by this native geometry item.
        """
        self.edge = edge

    def toShape(self) -> _PolylineEdge:
        """Return the shape represented by this sketch geometry item."""
        return self.edge


class _Vector:
    """Small vector stand-in for the FreeCAD Vector constructor."""

    def __init__(self, x: float, y: float, z: float = 0.0) -> None:
        """Store vector coordinates.

        Args:
            x: X coordinate.
            y: Y coordinate.
            z: Z coordinate.
        """
        self.x, self.y, self.z = x, y, z


class _Rotation:
    """Stand-in for a FreeCAD Rotation object."""

    def __init__(self, *_args: object) -> None:
        """Accept the axis and angle used by the sewing placement code.

        Args:
            _args: Rotation axis and angle passed by FreeCAD-facing code.
        """


class _Placement:
    """Stand-in for a FreeCAD Placement object."""

    def __init__(self, *_args: object) -> None:
        """Accept the translation and rotation used by sewing alignment.

        Args:
            _args: Translation and rotation passed by FreeCAD-facing code.
        """


@dataclass(frozen=True)
class _ProxyOptions:
    """Inputs controlling a sewing-proxy contract fixture."""

    width_a: float = 100.0
    width_b: float = 100.0
    start_a: float = 0.0
    end_a: float = 1.0
    start_b: float = 0.0
    end_b: float = 1.0
    reversed_b: bool = False
    tolerance: float = 0.5
    relative_tolerance: float = 0.05


def _fake_freecad() -> SimpleNamespace:
    """Build the minimal FreeCAD constructor surface needed by sewing tests.

    Returns:
        Namespace exposing Vector, Rotation and Placement constructors.
    """
    return SimpleNamespace(Vector=_Vector, Rotation=_Rotation, Placement=_Placement)


def _piece(
    piece_id: str,
    edges: tuple[_PolylineEdge, ...],
    placement: object | None = None,
) -> SimpleNamespace:
    """Build a Sketcher-authoritative pattern piece.

    Args:
        piece_id: Stable pattern-piece ID.
        edges: Native edges in Sketch.Geometry index order.
        placement: Optional native placement attached to the piece.

    Returns:
        Document-like pattern piece with linked sketch and semantic edge IDs.
    """
    edge_ids = tuple(f"{piece_id}:edge:{index}" for index in range(len(edges)))
    native_edges = tuple(edges)
    sketch = SimpleNamespace(
        Geometry=tuple(_Geometry(edge) for edge in native_edges),
        SemanticEdgeIds=edge_ids,
        Shape=SimpleNamespace(Edges=native_edges),
    )
    return SimpleNamespace(
        PieceId=piece_id,
        GeometryAuthority="Sketcher",
        Sketch=sketch,
        Shape=SimpleNamespace(Edges=native_edges),
        Placement=placement,
    )


def _seam(
    piece_a: SimpleNamespace,
    piece_b: SimpleNamespace,
    *,
    edge_a: int = 0,
    edge_b: int = 0,
    start_a: float = 0.0,
    end_a: float = 1.0,
    start_b: float = 0.0,
    end_b: float = 1.0,
    reversed_b: bool = False,
) -> SimpleNamespace:
    """Build a seam with stable semantic IDs and geometry signatures.

    Args:
        piece_a: Pattern piece supplying side A.
        piece_b: Pattern piece supplying side B.
        edge_a: Native Sketch.Geometry index on side A.
        edge_b: Native Sketch.Geometry index on side B.
        start_a: Normalized start fraction for side A.
        end_a: Normalized end fraction for side A.
        start_b: Normalized start fraction for side B.
        end_b: Normalized end fraction for side B.
        reversed_b: Whether side B should be traversed in reverse.

    Returns:
        Seam-like object containing the required native edge references.
    """
    return SimpleNamespace(
        SeamId="seam-test",
        Status="Valid",
        EdgeA=edge_a,
        EdgeAId=piece_a.Sketch.SemanticEdgeIds[edge_a],
        EdgeASignature="native-v1:side-a",
        StartA=start_a,
        EndA=end_a,
        EdgeB=edge_b,
        EdgeBId=piece_b.Sketch.SemanticEdgeIds[edge_b],
        EdgeBSignature="native-v1:side-b",
        StartB=start_b,
        EndB=end_b,
        ReversedB=reversed_b,
        Alignment="endpoints",
        StitchGroup="test-group",
    )


def _resolve_native_edge(
    piece: SimpleNamespace,
    edge_id: str,
    signature: str,
) -> dict[str, str | int]:
    """Resolve a test seam only when its semantic ID and signature are present.

    Args:
        piece: Pattern piece associated with this seam side.
        edge_id: Requested semantic edge identity.
        signature: Persisted native geometry signature.

    Returns:
        A record containing the exact semantic ID and an intentionally unrelated ordinal.

    Raises:
        MissingEdgeReference: If the semantic identity or signature is absent.
    """
    if edge_id not in piece.Sketch.SemanticEdgeIds or not signature:
        raise MissingEdgeReference("semantic seam edge reference is missing")
    return {"id": edge_id, "ordinal": 0}


def _execute_fake_proxy(options: _ProxyOptions | None = None) -> SimpleNamespace:
    """Run the production sewing proxy using native edge doubles.

    Args:
        options: Edge lengths, normalized ranges, reversal and mismatch tolerances.

    Returns:
        Sewing operation object populated by the production proxy.
    """
    settings = _ProxyOptions() if options is None else options
    piece_a = _piece(
        "front",
        (
            _PolylineEdge(
                ((0.0, 0.0), (settings.width_a, 0.0)),
            ),
        ),
    )
    piece_b = _piece(
        "back",
        (
            _PolylineEdge(
                ((0.0, 0.0), (settings.width_b, 0.0)),
            ),
        ),
    )
    seam = _seam(
        piece_a,
        piece_b,
        start_a=settings.start_a,
        end_a=settings.end_a,
        start_b=settings.start_b,
        end_b=settings.end_b,
        reversed_b=settings.reversed_b,
    )

    class _EmptyShape:
        """Shape placeholder used when the proxy creates its visual compound."""

    fake_part = SimpleNamespace(
        Shape=_EmptyShape,
        makePolygon=lambda values: tuple(values),
        makeLine=lambda start, end: (start, end),
        makeCompound=lambda values: tuple(values),
    )
    obj = SimpleNamespace(
        Seam=seam,
        PieceA=piece_a,
        PieceB=piece_b,
        Tolerance=settings.tolerance,
        RelativeTolerance=settings.relative_tolerance,
        Stitches=4,
        Alignment="endpoints",
        Status="Incomplete",
        CorrespondenceStatus="valid",
        LengthA=0.0,
        LengthB=0.0,
        LengthDifference=0.0,
        StitchCount=0,
        StitchPoints=[],
        Shape=None,
        ReversedB=False,
        AssemblyPlacementB=None,
    )
    SewingOperationProxy().execute(
        obj,
        app_module=_fake_freecad(),
        part_module=fake_part,
        vector_factory=_Vector,
        resolve_document_edge_fn=_resolve_native_edge,
    )
    return obj


def test_native_edge_uses_sketch_geometry_index() -> None:
    """Resolve the edge from Sketch.Geometry, not a cached piece shape."""
    authoritative = _PolylineEdge(((0.0, 0.0), (1.0, 0.0)))
    piece = _piece("front", (authoritative,))
    piece.Shape = SimpleNamespace(Edges=(object(), object()))
    assert _native_edge(piece, 0) is authoritative


def test_missing_native_sketch_authority_fails_closed() -> None:
    """Reject pieces whose only geometry comes from cached outline or dimensions."""
    piece = SimpleNamespace(PieceId="front", SewingOutline="[(0, 0), (1, 0), (1, 1)]")
    with pytest.raises(MissingEdgeReference, match="no native Sketcher authority"):
        _native_edge(piece, 0)


def test_native_shape_matching_uses_endpoints_not_shape_ordinal() -> None:
    """Match a native shape edge through its provenance endpoints, not its index."""
    wrong = SimpleNamespace(
        Vertexes=(
            SimpleNamespace(Point=SimpleNamespace(x=0.0, y=0.0)),
            SimpleNamespace(Point=SimpleNamespace(x=10.0, y=0.0)),
        )
    )
    expected = SimpleNamespace(
        Vertexes=(
            SimpleNamespace(Point=SimpleNamespace(x=0.0, y=5.0)),
            SimpleNamespace(Point=SimpleNamespace(x=10.0, y=5.0)),
        )
    )
    piece = _piece("front", (_PolylineEdge(((0.0, 0.0), (10.0, 0.0))),))
    piece.Sketch.Geometry = (object(),)
    piece.Sketch.Shape = SimpleNamespace(Edges=(wrong, expected))
    resolved = _native_edge(
        piece,
        0,
        native_edge_record_fn=lambda _piece, _index: {"points": ((0.0, 5.0), (10.0, 5.0))},
    )
    assert resolved is expected


def test_native_shape_matching_requires_unambiguous_provenance() -> None:
    """Reject a sketch shape edge when provenance cannot identify one exact match."""
    piece = _piece("front", (_PolylineEdge(((0.0, 0.0), (1.0, 0.0))),))
    piece.Sketch.Geometry = (object(),)
    piece.Sketch.Shape = SimpleNamespace(Edges=(_PolylineEdge(((10.0, 0.0), (11.0, 0.0))),))
    with pytest.raises(MissingEdgeReference, match="authoritative endpoint pair"):
        _native_edge(piece, 0, native_edge_record_fn=lambda _piece, _index: None)


def test_semantic_seam_id_maps_to_native_index_not_ir_ordinal() -> None:
    """Resolve a semantic ID through Sketch.SemanticEdgeIds, ignoring IR ordinals."""
    edges = tuple(_PolylineEdge(((float(i), 0.0), (float(i + 1), 0.0))) for i in range(8))
    piece = _piece("front", edges)
    seam = SimpleNamespace(
        SeamId="semantic-index",
        EdgeAId="front:edge:7",
        EdgeASignature="native-v1:signature",
    )
    resolver = lambda _piece, edge_id, _signature: {"id": edge_id, "ordinal": 1}
    assert _seam_edge_index(piece, seam, "A", resolve_document_edge_fn=resolver) == 7


def test_integer_only_seam_reference_is_rejected() -> None:
    """Reject obsolete seams that lack semantic edge IDs and signatures."""
    piece = _piece("front", (_PolylineEdge(((0.0, 0.0), (1.0, 0.0))),))
    with pytest.raises(MissingEdgeReference, match="semantic edge reference"):
        _seam_edge_index(piece, SimpleNamespace(SeamId="old-seam", EdgeA=0), "A")


def test_native_curve_length_uses_vectorized_segment_norms() -> None:
    """Compute curved-edge length from native discretization samples."""
    curve = _PolylineEdge(((0.0, 0.0), (2.0, 2.0), (4.0, 0.0)))
    piece = _piece("curved", (curve,))
    assert abs(_edge_length(piece, 0) - (8.0**0.5 * 2.0)) < 1e-9


def test_polyline_sampler_uses_normalized_arc_length() -> None:
    """Sample at half of the native curve's total arc length."""
    assert _sample_polyline(((0.0, 0.0), (2.0, 2.0), (4.0, 0.0)), 0.5) == (2.0, 2.0)


def test_seam_length_uses_selected_native_edge_range() -> None:
    """Compute seam length from its normalized range on a native edge."""
    piece_a = _piece("front", (_PolylineEdge(((0.0, 0.0), (100.0, 0.0))),))
    piece_b = _piece("back", (_PolylineEdge(((0.0, 0.0), (60.0, 0.0))),))
    seam = _seam(piece_a, piece_b, end_b=0.5)
    assert _seam_length(piece_a, seam, "A", resolve_document_edge_fn=_resolve_native_edge) == 100.0
    assert _seam_length(piece_b, seam, "B", resolve_document_edge_fn=_resolve_native_edge) == 30.0


def test_correspondence_reverses_side_b_once() -> None:
    """Reverse B's samples once after both sides have been sampled in native order."""
    edge = _PolylineEdge(((0.0, 0.0), (100.0, 0.0)))
    piece = _piece("front", (edge,))
    seam = _seam(piece, piece, start_a=0.2, end_a=0.8, start_b=0.2, end_b=0.8, reversed_b=True)
    pairs = _seam_correspondence(
        piece,
        piece,
        seam,
        3,
        "endpoints",
        vector_factory=_Vector,
        resolve_document_edge_fn=_resolve_native_edge,
    )
    assert pairs[0][1].x == 80.0
    assert pairs[-1][1].x == 20.0


def test_boundary_sampling_honors_normalized_range() -> None:
    """Retain only samples inside the requested normalized boundary interval."""
    assert _sample_boundary((10, 11, 12, 13, 14), 0.0, 1.0, 5) == [10, 11, 12, 13, 14]
    assert _sample_boundary((10, 11, 12, 13, 14), 0.25, 0.75, 3) == [11, 12, 13]


def test_proxy_validates_reversed_native_seam_correspondence() -> None:
    """Run the real proxy and verify its generated stitch correspondence."""
    obj = _execute_fake_proxy(_ProxyOptions(reversed_b=True))
    assert obj.Status == "Valid"
    assert obj.StitchCount == 4
    assert len(obj.StitchPoints) == 4
    assert obj.ReversedB is True
    assert obj.StitchPoints[0].split("|")[1].startswith("100.000000")


def test_proxy_reports_relative_length_mismatch_symmetrically() -> None:
    """Reject seam mismatch regardless of which side is longer."""
    forward = _execute_fake_proxy(_ProxyOptions(width_a=100.0, width_b=120.0))
    reverse = _execute_fake_proxy(_ProxyOptions(width_a=120.0, width_b=100.0))
    assert forward.CorrespondenceStatus == "length_mismatch"
    assert reverse.CorrespondenceStatus == "length_mismatch"


def test_proxy_reports_mismatch_for_selected_subrange() -> None:
    """Compare lengths over the selected normalized interval, not the whole edge."""
    obj = _execute_fake_proxy(_ProxyOptions(start_b=0.0, end_b=0.5))
    assert obj.LengthA == 100.0
    assert obj.LengthB == 50.0
    assert obj.CorrespondenceStatus == "length_mismatch"
