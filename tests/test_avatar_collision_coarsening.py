from freecad_cloth.avatar.AvatarCollision import CollisionSurface, coarsen_collision_surface


def _triangle(center, scale):
    x, y, z = center
    s = float(scale)
    return (
        (x + 2.0 * s / 3.0, y - s / 3.0, z - s / 3.0),
        (x - s / 3.0, y + 2.0 * s / 3.0, z - s / 3.0),
        (x - s / 3.0, y - s / 3.0, z + 2.0 * s / 3.0),
    )


def _surface():
    centers_and_scales = (
        ((0.0, 0.0, 0.0), 0.1),
        ((0.1, 0.1, 0.1), 2.0),
        ((10.0, 10.0, 10.0), 0.5),
        ((20.0, 20.0, 20.0), 3.0),
    )
    vertices = []
    triangles = []
    for center, scale in centers_and_scales:
        start = len(vertices)
        vertices.extend(_triangle(center, scale))
        triangles.append((start, start + 1, start + 2))
    return CollisionSurface(tuple(vertices), tuple(triangles), region="avatar", thickness=1.25)


def test_area_ranked_coarsening_is_deterministic_and_preserves_budget():
    surface = _surface()
    first = coarsen_collision_surface(surface, max_triangles=3)
    second = coarsen_collision_surface(surface, max_triangles=3)

    assert len(first.triangles) == 3
    assert len(set(first.triangles)) == 3
    assert first.triangles == second.triangles
    assert first.vertices == surface.vertices
    assert first.region == "avatar"
    assert first.thickness == 1.25


def test_area_ranked_coarsening_prefers_largest_cell_face_and_ranked_fill():
    surface = _surface()
    result = coarsen_collision_surface(surface, max_triangles=3)

    assert surface.triangles[1] in result.triangles
    assert surface.triangles[2] in result.triangles
    assert surface.triangles[3] in result.triangles
    assert surface.triangles[0] not in result.triangles


def test_area_ranked_coarsening_returns_original_surface_under_budget():
    surface = _surface()
    result = coarsen_collision_surface(surface, max_triangles=len(surface.triangles))

    assert result == surface
