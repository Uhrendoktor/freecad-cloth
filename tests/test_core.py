import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PatternModel import PatternPiece, Seam
from PatternGeometry import LineSegment, ParametricPattern, QuadraticBezier, rectangle
from PatternSchema import PatternDocument, dumps, loads
from SimulationBackend import ClothState, NullSolver


def test_pattern_piece_validation():
    piece = PatternPiece("front", [(0, 0), (10, 0), (10, 10)], 5, id="front")
    piece.validate()


def test_invalid_piece():
    try:
        PatternPiece("", [(0, 0), (1, 0), (0, 1)], id="x").validate()
    except ValueError:
        return
    raise AssertionError("empty name should fail")


def test_seam_validation():
    Seam("front", 0, "back", 2, id="shoulder").validate()


def test_rectangle_is_closed_and_stable():
    first = rectangle(100, 60)
    second = rectangle(100, 60)
    assert [s.id for s in first.segments] == ["bottom", "right", "top", "left"]
    assert first.sampled_outline() == second.sampled_outline()
    assert first.lengths() == second.lengths()


def test_parametric_dimensions_change_geometry_not_topology():
    small = rectangle(100, 60)
    large = rectangle(120, 80)
    assert [s.id for s in small.segments] == [s.id for s in large.segments]
    assert large.lengths()["bottom"] == 120
    assert large.lengths()["right"] == 80


def test_quadratic_bezier_is_sampleable():
    curve = QuadraticBezier("armhole", (0, 0), (5, 10), (10, 0))
    assert curve.point(0) == (0, 0)
    assert curve.point(1) == (10, 0)
    assert len(curve.polyline(5)) == 5


def test_custom_closed_curve_pattern():
    pattern = ParametricPattern([
        LineSegment("bottom", (0, 0), (10, 0)),
        LineSegment("right", (10, 0), (10, 5)),
        QuadraticBezier("top", (10, 5), (5, 9), (0, 5)),
        LineSegment("left", (0, 5), (0, 0)),
    ])
    assert set(pattern.by_id()) == {"bottom", "right", "top", "left"}
    assert pattern.lengths()["top"] > 10


def test_invalid_geometry_is_rejected():
    try:
        ParametricPattern([
            LineSegment("a", (0, 0), (1, 0)),
            LineSegment("b", (2, 0), (2, 1)),
            LineSegment("c", (2, 1), (0, 0)),
        ])
    except ValueError:
        return
    raise AssertionError("open boundary should fail")


def test_pattern_document_round_trip_is_canonical():
    document = PatternDocument(
        "garment-1", "Test garment",
        pieces=[{"id": "front", "name": "Front"}, {"id": "back", "name": "Back"}],
        seams=[{"id": "side", "piece_a": "front", "piece_b": "back"}],
        metadata={"units": "mm"},
    )
    encoded = dumps(document)
    restored = loads(encoded)
    assert dumps(restored) == encoded


def test_pattern_document_rejects_malformed_input():
    for text in ["[]", "{\"schema_version\": 99, \"pattern_id\": \"x\", \"name\": \"x\"}"]:
        try:
            loads(text)
        except ValueError:
            continue
        raise AssertionError("malformed document should fail")


def test_null_solver_is_deterministic():
    state = ClothState([(0.0, 0.0, 0.0)])
    assert NullSolver().step(state, 0.01) == state


def run():
    for name, fn in globals().copy().items():
        if name.startswith("test_"):
            fn()
    print("core tests passed")


if __name__ == "__main__":
    run()
