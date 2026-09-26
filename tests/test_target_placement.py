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


def test_nearest_projection_allows_explicit_outward_context_without_disabling_default_fail_closed():
    surface = CollisionSurface(
        vertices=(
            (-10.0, -10.0, 0.0), (10.0, -10.0, 0.0), (0.0, 10.0, 0.0),
            (-10.0, -10.0, 0.0), (0.0, 10.0, 0.0), (10.0, -10.0, 0.0),
        ),
        triangles=((0, 1, 2), (3, 4, 5)),
    )
    projection = nearest_target_projection(
        (0.0, 0.0, 5.0),
        surface,
        preferred_normal=(0.0, 0.0, 1.0),
    )
    assert projection.normal == (0.0, 0.0, 1.0)


def test_average_point_is_deterministic():
    assert average_point(((0.0, 0.0, 2.0), (2.0, 4.0, 4.0))) == (1.0, 2.0, 3.0)


def test_group_fit_contract_preserves_authored_spacing_and_uses_one_shared_translation():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    source = (root / "freecad_cloth" / "avatar" / "FittingCommands.py").read_text(encoding="utf-8")
    start = source.index("def snap_pattern_pieces_to_target(")
    end = source.index("\ndef position_piece", start)
    body = source[start:end]
    assert "total_translation = App.Vector(0.0, 0.0, 0.0)" in body
    assert "for _iteration in range(16)" in body
    assert "piece.Placement = App.Placement(" in body
    assert "scene.HomePlacements" in body
    assert "scene.PiecePlacements = list(persisted_before)" in body
    assert "piece.Placement = original" in body
    assert body.count("minimum_signed_clearance(") == 1
    assert "sample_cache = {" in body
    assert "sample_cache[piece] = tuple(" in body
    loop_start = body.index("for _iteration in range(16):")
    loop_end = body.index("final_reports = [", loop_start)
    assert "minimum_signed_clearance(" not in body[loop_start:loop_end]
    assert "PatternSimulationAdapter" in source
    assert "PatternMesh" in source
    assert "shared rigid" in body.lower()


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
    end = source.index("\ndef position_piece", start)
    body = source[start:end]
    assert "placement.Rotation.Axis" in body
    assert "PiecePlacement(" in body


def test_target_link_is_part_of_transactional_rollback_contract():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "freecad_cloth" / "avatar" / "FittingCommands.py").read_text(encoding="utf-8")
    start = source.index("def snap_pattern_pieces_to_target(")
    end = source.index("\ndef position_piece", start)
    body = source[start:end]
    assert "target_before = getattr(scene, \"DrapeTarget\", None)" in body
    assert "scene.DrapeTarget = target_before" in body


def test_group_fit_rejects_positive_clearance_without_target_proximity():
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1]
        / "freecad_cloth"
        / "avatar"
        / "FittingCommands.py"
    ).read_text(encoding="utf-8")
    start = source.index("def snap_pattern_pieces_to_target(")
    end = source.index("\\ndef position_piece", start)
    body = source[start:end]
    assert "nearest_target_projection" in body
    assert "proximity_error" in body
    assert "previous_proximity_error" in body
    assert "did not reduce target proximity error" in body
    assert "stopped %.3f mm from target alignment" in body
    assert "Clearance is proven against the exact PatternMesh" in body or "exact PatternMesh" in body


def test_indexed_projection_matches_bruteforce_on_subdivided_surface():
    from math import isclose
    from freecad_cloth.avatar.TargetPlacement import (
        _closest_point_on_triangle,
        _oriented_outward_normal,
    )

    rows = 12
    vertices = []
    for y in range(rows + 1):
        for x in range(rows + 1):
            vertices.append((float(x * 10.0), float(y * 10.0), 0.0))
    triangles = []
    width = rows + 1
    for y in range(rows):
        for x in range(rows):
            a = y * width + x
            b = a + 1
            c0 = a + width
            d = c0 + 1
            triangles.extend(((a, b, d), (a, d, c0)))
    surface = CollisionSurface(tuple(vertices), tuple(triangles))

    def brute(point):
        center = surface.center
        best = None
        for index, triangle in enumerate(surface.triangles):
            a, b, c = (surface.vertices[int(i)] for i in triangle)
            normal = _oriented_outward_normal(a, b, c, center)
            closest = _closest_point_on_triangle(point, a, b, c)
            distance = sum(
                (float(point[i]) - float(closest[i])) ** 2 for i in range(3)
            ) ** 0.5
            if best is None or distance < best.distance - 1e-12:
                best = type("Result", (), {
                    "point": closest,
                    "normal": normal,
                    "distance": distance,
                })()
        return best

    for point in ((5.1, 7.3, 14.0), (61.4, 93.2, 8.0), (117.2, 21.7, 19.0)):
        indexed = nearest_target_projection(point, surface)
        expected = brute(point)
        assert isclose(indexed.distance, expected.distance, rel_tol=0.0, abs_tol=1e-9)
        assert all(
            isclose(indexed.point[i], expected.point[i], rel_tol=0.0, abs_tol=1e-9)
            for i in range(3)
        )
        assert indexed.normal == expected.normal
