# Copyright (C) 2026 FreeCAD Cloth contributors
from types import SimpleNamespace

import pytest

from freecad_cloth.pattern.PatternTopologyRepair import (
    InvalidRepairTarget,
    TopologyRepairError,
    build_repair_plan,
    current_edge_candidates,
    seam_reference_status,
)
from freecad_cloth.pattern.SeamReference import capture_edge_reference


def _piece(
    piece_id: str = "front",
    points: tuple[tuple[float, float], ...] = (
        (0.0, 0.0),
        (10.0, 0.0),
        (10.0, 10.0),
        (0.0, 10.0),
    ),
) -> SimpleNamespace:
    """Create a PatternPiece test double backed by native Sketcher lines."""

    class Point:
        """Coordinate value exposed by native Sketcher line geometry."""

        def __init__(self, x: float, y: float) -> None:
            self.x, self.y, self.z = float(x), float(y), 0.0

    class LineSegment:
        """Sketcher-style line recognized by the PatternIR adapter."""

        def __init__(self, start: tuple[float, float], end: tuple[float, float]) -> None:
            self.StartPoint = Point(*start)
            self.EndPoint = Point(*end)

    geometry = tuple(
        LineSegment(start, points[(index + 1) % len(points)]) for index, start in enumerate(points)
    )
    sketch = SimpleNamespace(
        Geometry=geometry,
        SemanticEdgeIds=tuple(f"{piece_id}:edge:{index}" for index in range(len(geometry))),
        getConstruction=lambda _index: False,
    )
    return SimpleNamespace(
        PieceId=piece_id,
        Label=piece_id,
        GeometryAuthority="Sketcher",
        Sketch=sketch,
        DraftingBoundary=repr(points),
        SewingOutline=repr(points),
        SeamAllowance=0.0,
        GrainlineAngle=0.0,
    )


def _seam(piece_a, edge_a=0, piece_b=None, edge_b=0):
    piece_b = piece_b or _piece("back")
    records_a = current_edge_candidates(SimpleNamespace(PatternA=piece_a, PatternB=piece_b), "A")
    records_b = current_edge_candidates(SimpleNamespace(PatternA=piece_a, PatternB=piece_b), "B")
    ref_a = capture_edge_reference(
        piece_a.PieceId,
        records_a[edge_a]["id"],
        records_a[edge_a]["points"],
        records_a[edge_a]["provenance"],
    )
    ref_b = capture_edge_reference(
        piece_b.PieceId,
        records_b[edge_b]["id"],
        records_b[edge_b]["points"],
        records_b[edge_b]["provenance"],
    )
    return SimpleNamespace(
        SeamId="front-seam",
        Label="front seam",
        PatternA=piece_a,
        PatternB=piece_b,
        EdgeAId=ref_a.edge_id,
        EdgeASignature=ref_a.signature,
        EdgeBId=ref_b.edge_id,
        EdgeBSignature=ref_b.signature,
    )


def test_changed_reference_is_reported_before_repair():
    original = _piece()
    seam = _seam(original)
    seam.PatternA = _piece(points=((0, 0), (12, 0), (10, 10), (0, 10)))
    assert seam_reference_status(seam, "A") == (False, "changed")


def test_missing_reference_can_be_explicitly_mapped_to_current_edge():
    piece = _piece()
    seam = _seam(piece)
    seam.EdgeAId = "front:edge:99"
    seam.EdgeASignature = "missing"
    target = current_edge_candidates(seam, "A")[2]["id"]
    plan = build_repair_plan([(seam, "A", target)])
    assert len(plan) == 1
    assert plan[0][2]["id"] == target


def test_repair_target_must_be_a_current_semantic_edge():
    seam = _seam(_piece())
    with pytest.raises(InvalidRepairTarget):
        build_repair_plan([(seam, "A", "front:edge:404")])


def test_duplicate_side_mapping_is_rejected_before_mutation():
    seam = _seam(_piece())
    edge = current_edge_candidates(seam, "A")[1]["id"]
    with pytest.raises(TopologyRepairError, match="duplicate repair target"):
        build_repair_plan([(seam, "A", edge), (seam, "A", edge)])
