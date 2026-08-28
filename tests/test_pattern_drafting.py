import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PatternDrafting import default_points, parse_points, serialize_points, move_point, seam_allowance_preview


def test_boundary_roundtrip_and_move():
    points = default_points(100, 60)
    assert parse_points(serialize_points(points)) == points
    moved = move_point(points, 1, 125, 0)
    assert moved[1] == (125.0, 0.0)
    assert moved[0] == points[0]


def test_allowance_preview_is_persistable_geometry():
    points = default_points(100, 60)
    preview = seam_allowance_preview(points, 5)
    assert preview[0] == (-5.0, -5.0)
    assert preview[2] == (105.0, 65.0)


if __name__ == "__main__":
    test_boundary_roundtrip_and_move(); test_allowance_preview_is_persistable_geometry(); print("pattern drafting tests passed")
