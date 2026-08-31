import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freecad_cloth.pattern.PatternGeometry import LineSegment, ParametricPattern, QuadraticBezier, rectangle
from freecad_cloth.pattern.PatternDerivedGeometry import Notch, add_notches, derive_cut_boundary, notch_point


def test_zero_allowance_preserves_sewing_boundary():
    pattern = rectangle(100, 60)
    derived = derive_cut_boundary(pattern, 0)
    assert [edge.points for edge in derived.cut_boundary] == [
        (segment.start, segment.end) for segment in pattern.segments
    ]


def test_rectangle_allowance_is_outward_and_deterministic():
    pattern = rectangle(100, 60)
    first = derive_cut_boundary(pattern, 5)
    second = derive_cut_boundary(pattern, 5)
    assert first == second
    assert first.sewing_boundary is pattern
    assert first.cut_boundary[0].points[0] == (0.0, -5.0)
    assert first.cut_boundary[0].points[1] == (100.0, -5.0)


def test_per_edge_override_and_curve_are_supported():
    pattern = ParametricPattern([
        LineSegment("bottom", (0, 0), (10, 0)),
        LineSegment("right", (10, 0), (10, 5)),
        QuadraticBezier("top", (10, 5), (5, 9), (0, 5)),
        LineSegment("left", (0, 5), (0, 0)),
    ])
    derived = derive_cut_boundary(pattern, 2, {"right": 4}, curve_samples=8)
    assert derived.cut_boundary[1].points[0] == (14.0, 0.0)
    assert len(derived.cut_boundary[2].points) == 8


def test_notches_use_stable_segment_ids_and_normalized_positions():
    pattern = rectangle(100, 60)
    derived = derive_cut_boundary(pattern, 5)
    derived = add_notches(derived, [Notch("waist", "right", 0.5)])
    assert notch_point(pattern, derived.notches[0]) == (100.0, 30.0)
    assert derived.notches[0].id == "waist"


def test_invalid_allowance_and_notch_references_are_rejected():
    pattern = rectangle(10, 10)
    try:
        derive_cut_boundary(pattern, -1)
    except ValueError:
        pass
    else:
        raise AssertionError("negative allowance should fail")
    try:
        add_notches(derive_cut_boundary(pattern, 1), [Notch("bad", "missing", 0.5)])
    except ValueError:
        pass
    else:
        raise AssertionError("unknown notch segment should fail")
