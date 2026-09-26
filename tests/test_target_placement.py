from math import isclose

from freecad_cloth.avatar.AvatarCollision import CollisionSurface
from freecad_cloth.avatar.TargetPlacement import average_point, minimum_signed_clearance, nearest_target_projection


def _top_surface():
    return CollisionSurface(
        vertices=(
            (-10.0, -10.0, 0.0),
            (10.0, -10.0, 0.0),
            (10.0, 10.0, 0.0),
            (-10.0, 10.0, 0.0),
        ),
        triangles=((0, 1, 2), (0, 2, 3)),
    )


def test_nearest_projection_reports_outward_normal_and_distance():
    projection = nearest_target_projection((0.0, 0.0, 5.0), _top_surface())
    assert projection.normal == (0.0, 0.0, 1.0)
    assert isclose(projection.point[2], 0.0)
    assert isclose(projection.distance, 5.0)


def test_signed_clearance_rejects_points_inside_target():
    surface = _top_surface()
    assert isclose(minimum_signed_clearance(((0.0, 0.0, 4.0),), surface).minimum_signed_clearance, 4.0)
    assert isclose(minimum_signed_clearance(((0.0, 0.0, -4.0),), surface).minimum_signed_clearance, -4.0)


def test_nearest_projection_fails_closed_on_opposing_ambiguous_normals():
    surface = CollisionSurface(
        vertices=(
            (-10.0, -10.0, 0.0), (10.0, -10.0, 0.0), (0.0, 10.0, 0.0),
            (-10.0, -10.0, 0.0), (0.0, 10.0, 0.0), (10.0, -10.0, 0.0),
        ),
        triangles=((0, 1, 2), (3, 4, 5)),
    )
    try:
        nearest_target_projection((0.0, 0.0, 5.0), surface)
    except ValueError as exc:
        assert "ambiguous" in str(exc)
    else:
        raise AssertionError("opposing equally-near target normals must fail closed")


def test_average_point_is_deterministic():
    assert average_point(((0.0, 0.0, 2.0), (2.0, 4.0, 4.0))) == (1.0, 2.0, 3.0)


def test_group_fit_contract_preserves_authored_spacing_and_uses_one_shared_translation():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    source = (root / "freecad_cloth" / "avatar" / "FittingCommands.py").read_text(encoding="utf-8")
    start = source.index("def snap_pattern_pieces_to_target(")
    end = source.index("\ndef position_piece", start)
    body = source[start:end]
    assert "shared = tuple(" in body
    assert "piece.Placement = App.Placement(" in body
    assert "scene.HomePlacements" in body
    assert "scene.PiecePlacements = list(persisted_before)" in body
    assert "piece.Placement = original" in body
    assert body.count("minimum_signed_clearance(") >= 2


def test_target_surface_is_transformed_to_world_coordinates():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    source = (root / "freecad_cloth" / "avatar" / "FittingCommands.py").read_text(encoding="utf-8")
    assert "placement.multVec(App.Vector(*point))" in source
    assert "CollisionSurface(tuple(world_vertices)" in source


def test_group_fit_persists_rotation_axis_in_piece_placement_source_contract():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "freecad_cloth" / "avatar" / "FittingCommands.py").read_text(encoding="utf-8")
    start = source.index("def snap_pattern_pieces_to_target(")
    end = source.index("
def position_piece", start)
    body = source[start:end]
    assert "placement.Rotation.Axis" in body
    assert "PiecePlacement(" in body
