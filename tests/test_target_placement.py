from freecad_cloth.avatar.AvatarCollision import CollisionSurface
from freecad_cloth.avatar.TargetPlacement import (
    _closest_point_on_triangle,
    _outward_normal,
    _target_surface_query_candidate_count,
    nearest_surface_distance,
    point_inside_closed_surface,
    target_surface_anchor,
    translation_to_target,
)


def _plane(z=0.0):
    surface = CollisionSurface(
        ((-50.0, -50.0, z), (50.0, -50.0, z), (50.0, 50.0, z), (-50.0, 50.0, z)),
        ((0, 1, 2), (0, 2, 3)),
        "target",
    )
    surface.validate()
    return surface


def test_anchor_uses_nearest_surface_and_outward_normal():
    hit = target_surface_anchor(_plane(), (0.0, 0.0, 25.0))
    assert hit.triangle_index in (0, 1)
    assert hit.point == (0.0, 0.0, 0.0)
    assert hit.normal == (0.0, 0.0, 1.0)
    assert hit.distance == 25.0


def test_translation_to_target_is_bounded():
    delta, hit = translation_to_target(_plane(), (0.0, 0.0, 25.0), clearance=8.0, max_translation=20.0)
    assert delta == (0.0, 0.0, -17.0)
    assert hit.normal == (0.0, 0.0, 1.0)


def test_translation_to_target_rejects_excessive_travel():
    try:
        translation_to_target(_plane(), (0.0, 0.0, 100.0), clearance=8.0, max_translation=50.0)
    except ValueError as exc:
        assert "translation bound" in str(exc)
    else:
        raise AssertionError("excessive target travel was accepted")


def test_nearest_surface_distance_is_surface_based():
    assert nearest_surface_distance(_plane(), ((0.0, 0.0, 12.5),)) == 12.5


def _box(size=20.0):
    h = float(size) / 2.0
    vertices = (
        (-h, -h, -h), (h, -h, -h), (h, h, -h), (-h, h, -h),
        (-h, -h, h), (h, -h, h), (h, h, h), (-h, h, h),
    )
    triangles = (
        (0, 2, 1), (0, 3, 2),
        (4, 5, 6), (4, 6, 7),
        (0, 1, 5), (0, 5, 4),
        (1, 2, 6), (1, 6, 5),
        (2, 3, 7), (2, 7, 6),
        (3, 0, 4), (3, 4, 7),
    )
    surface = CollisionSurface(vertices, triangles, "target")
    surface.validate()
    return surface


def test_closed_surface_classifies_inside_and_outside():
    surface = _box()
    assert point_inside_closed_surface(surface, (0.0, 0.0, 0.0)) is True
    assert point_inside_closed_surface(surface, (20.0, 0.0, 0.0)) is False


def test_closed_surface_rejects_open_surface():
    surface = _plane()
    try:
        point_inside_closed_surface(surface, (0.0, 0.0, 1.0))
    except ValueError as exc:
        assert "not closed" in str(exc)
    else:
        raise AssertionError("open target surface was accepted as closed")


def test_translation_anchor_is_outside_after_bounded_move():
    surface = _box()
    delta, _hit = translation_to_target(surface, (0.0, 0.0, 30.0), clearance=8.0, max_translation=30.0)
    placed = (0.0 + delta[0], 0.0 + delta[1], 30.0 + delta[2])
    assert point_inside_closed_surface(surface, placed) is False
    assert nearest_surface_distance(surface, (placed,)) >= 8.0 - 1e-6


def test_minimum_outward_clearance_rejects_inward_points():
    from freecad_cloth.avatar.TargetPlacement import minimum_outward_clearance
    assert minimum_outward_clearance(_plane(), ((0.0, 0.0, 8.0),)) == 8.0
    assert minimum_outward_clearance(_plane(), ((0.0, 0.0, -2.0),)) < 0.0


def test_coplanar_adjacent_triangles_at_shared_edge_are_not_ambiguous():
    hit = target_surface_anchor(_plane(), (0.0, 0.0, 25.0))
    assert hit.normal == (0.0, 0.0, 1.0)


def test_closed_convex_corner_tie_resolves_deterministically():
    surface = _box()
    hits = [target_surface_anchor(surface, (15.0, 0.0, 15.0)) for _ in range(3)]
    assert all(hit.distance == 5.0 for hit in hits)
    assert len({hit.triangle_index for hit in hits}) == 1
    assert hits[0].normal in ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0))


def test_closed_concave_local_edge_tie_resolves_without_ambiguity():
    surface = _concave_prism()
    hit = target_surface_anchor(surface, (0.75, 0.75, 0.0))
    assert hit.distance == 0.25
    assert hit.normal in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0))


def test_disconnected_near_equal_normals_remain_fail_closed():
    surface = _disconnected_orthogonal_tie_surface()
    try:
        target_surface_anchor(surface, (3.0, 0.0, 3.0))
    except ValueError as exc:
        assert "ambiguous" in str(exc)
    else:
        raise AssertionError("non-local normal tie was silently resolved")


def _concave_prism():
    polygon = (
        (0.0, 0.0), (2.0, 0.0), (2.0, 2.0),
        (1.0, 2.0), (1.0, 1.0), (0.0, 1.0),
    )
    vertices = tuple(
        (x, y, z)
        for z in (-1.0, 1.0)
        for x, y in polygon
    )
    n = len(polygon)
    triangles = []
    for i in range(1, n - 1):
        triangles.append((0, i + 1, i))
        triangles.append((n, n + i, n + i + 1))
    for i in range(n):
        j = (i + 1) % n
        triangles.extend((
            (i, j, n + j),
            (i, n + j, n + i),
        ))
    surface = CollisionSurface(vertices, tuple(triangles), "target")
    surface.validate()
    return surface


def _disconnected_orthogonal_tie_surface():
    vertices = (
        (-10.0, -10.0, 0.0), (10.0, -10.0, 0.0), (-10.0, 10.0, 0.0),
        (0.0, -10.0, -10.0), (0.0, 10.0, -10.0), (0.0, -10.0, 10.0),
    )
    surface = CollisionSurface(
        vertices,
        ((0, 1, 2), (3, 4, 5)),
        "target",
    )
    surface.validate()
    return surface


def _reference_anchor(surface, point):
    center = surface.center
    candidates = []
    for triangle_index, triangle in enumerate(surface.triangles):
        a, b, c = (surface.vertices[index] for index in triangle)
        try:
            normal = _outward_normal(a, b, c, center)
        except ValueError:
            continue
        closest = _closest_point_on_triangle(point, a, b, c)
        distance = sum((float(point[axis]) - float(closest[axis])) ** 2 for axis in range(3)) ** 0.5
        candidates.append((distance, triangle_index, closest, normal))
    return min(candidates, key=lambda value: (value[0], value[1]))


def _large_grid_surface(cells=114):
    vertices = tuple(
        (float(x), float(y), 0.0)
        for y in range(cells + 1)
        for x in range(cells + 1)
    )
    triangles = []
    stride = cells + 1
    for y in range(cells):
        for x in range(cells):
            i = y * stride + x
            triangles.append((i, i + 1, i + stride + 1))
            triangles.append((i, i + stride + 1, i + stride))
    surface = CollisionSurface(tuple(vertices), tuple(triangles), "target")
    surface.validate()
    assert len(surface.triangles) == 25992
    return surface


def test_bvh_anchor_matches_exact_reference():
    for point in ((0.0, 0.0, 25.0), (7.5, -3.0, 12.25)):
        surface = _plane()
        expected = _reference_anchor(surface, point)
        actual = target_surface_anchor(surface, point)
        assert actual.triangle_index == expected[1]
        assert actual.point == expected[2]
        assert actual.normal == expected[3]
        assert actual.distance == expected[0]


def test_bvh_prunes_26k_triangle_target_without_wall_clock_gate():
    surface = _large_grid_surface()
    point = (57.25, 57.25, 25.0)
    hit = target_surface_anchor(surface, point)
    assert hit.distance == 25.0
    assert hit.normal == (0.0, 0.0, 1.0)
    assert _target_surface_query_candidate_count(surface, point) < 512

