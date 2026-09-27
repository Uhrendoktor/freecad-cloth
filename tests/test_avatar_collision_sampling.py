from freecad_cloth.avatar.AvatarCollision import CollisionSurface, coarsen_collision_surface


def _surface_with_corner_and_interior_triangles():
    centers = [
        (0.0, 0.0, 0.0), (0.0, 0.0, 100.0),
        (0.0, 100.0, 0.0), (0.0, 100.0, 100.0),
        (10.0, 0.0, 0.0), (10.0, 0.0, 100.0),
        (10.0, 100.0, 0.0), (10.0, 100.0, 100.0),
    ]
    centers.extend((5.0, float(y), float(z)) for y in range(10, 100, 10) for z in range(10, 100, 10))
    vertices = []
    triangles = []
    for index, (x, y, z) in enumerate(centers):
        offset = len(vertices)
        vertices.extend(((x - 0.2, y, z), (x + 0.1, y + 0.2, z), (x + 0.1, y, z + 0.2)))
        triangles.append((offset, offset + 1, offset + 2))
    return CollisionSurface(tuple(vertices), tuple(triangles), region='avatar', thickness=1.25), centers


def test_coarsen_farthest_point_sampling_is_deterministic_and_budgeted():
    surface, _ = _surface_with_corner_and_interior_triangles()

    first = coarsen_collision_surface(surface, max_triangles=16)
    second = coarsen_collision_surface(surface, max_triangles=16)

    assert len(first.triangles) == 16
    assert len(set(first.triangles)) == 16
    assert first.triangles == second.triangles
    assert first.vertices == surface.vertices
    assert first.region == 'avatar'
    assert first.thickness == 1.25


def test_coarsen_preserves_anisotropic_spatial_extrema():
    surface, centers = _surface_with_corner_and_interior_triangles()
    result = coarsen_collision_surface(surface, max_triangles=9)

    source_index = {triangle: index for index, triangle in enumerate(surface.triangles)}
    selected_centers = {centers[source_index[triangle]] for triangle in result.triangles}

    extrema = {
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 100.0),
        (0.0, 100.0, 0.0),
        (0.0, 100.0, 100.0),
        (10.0, 0.0, 0.0),
        (10.0, 0.0, 100.0),
        (10.0, 100.0, 0.0),
        (10.0, 100.0, 100.0),
    }
    assert extrema.issubset(set(selected_centers))
    assert len(result.triangles) == 9