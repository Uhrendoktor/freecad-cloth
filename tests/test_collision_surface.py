from freecad_cloth.shared.collision import coarsen_collision_surface, surface_from_triangles


def _cube_surface():
    vertices = (
        (-1.0, -1.0, -1.0),
        (1.0, -1.0, -1.0),
        (1.0, 1.0, -1.0),
        (-1.0, 1.0, -1.0),
        (-1.0, -1.0, 1.0),
        (1.0, -1.0, 1.0),
        (1.0, 1.0, 1.0),
        (-1.0, 1.0, 1.0),
    )
    triangles = (
        (0, 1, 2), (0, 2, 3),
        (4, 6, 5), (4, 7, 6),
        (0, 4, 5), (0, 5, 1),
        (1, 5, 6), (1, 6, 2),
        (2, 6, 7), (2, 7, 3),
        (3, 7, 4), (3, 4, 0),
    )
    return surface_from_triangles(vertices, triangles)


def _boundary_edge_count(triangles):
    counts = {}
    for triangle in triangles:
        for left, right in (
            (triangle[0], triangle[1]),
            (triangle[1], triangle[2]),
            (triangle[2], triangle[0]),
        ):
            edge = tuple(sorted((int(left), int(right))))
            counts[edge] = counts.get(edge, 0) + 1
    return sum(1 for count in counts.values() if count != 2)


def test_closed_collision_surface_is_preserved_even_below_triangle_budget():
    source = _cube_surface()
    reduced = coarsen_collision_surface(source, max_triangles=6)
    assert reduced is source
    assert len(reduced.triangles) == len(source.triangles)
    assert _boundary_edge_count(reduced.triangles) == 0


def test_closed_collision_surface_never_uses_open_surface_coarsening():
    source = _cube_surface()
    reduced = coarsen_collision_surface(source, max_triangles=1)
    assert reduced is source
    assert len(reduced.vertices) == len(source.vertices)
    assert len(reduced.triangles) == len(source.triangles)
