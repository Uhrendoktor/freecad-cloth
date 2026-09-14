from freecad_cloth.common.MeshValidation import (
    nearest_surface_clearance,
    nearest_target_clearance,
    validate_mesh,
)


def _approx(actual, expected, tolerance=1e-9):
    if abs(float(actual) - float(expected)) > tolerance:
        raise AssertionError(f"expected {expected!r}, got {actual!r}")


def _raises(exc_type, message, function):
    try:
        function()
    except exc_type as exc:
        if message not in str(exc):
            raise AssertionError(f"expected {message!r} in {exc!r}") from exc
    else:
        raise AssertionError(f"expected {exc_type.__name__}")


def square_mesh():
    vertices = ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 10.0, 0.0), (0.0, 10.0, 0.0))
    triangles = ((0, 1, 2), (0, 2, 3))
    return vertices, triangles


def test_validation_fallback_is_deterministic():
    vertices, triangles = square_mesh()
    result = validate_mesh(vertices, triangles, prefer_trimesh=False)
    assert result.vertices == 4
    assert result.faces == 2
    assert result.components == 1
    assert result.bounds == (0.0, 10.0, 0.0, 10.0, 0.0, 0.0)
    assert result.degenerate_faces == 0
    assert result.watertight is None


def test_validation_fallback_counts_disconnected_components():
    vertices = (
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (10.0, 0.0, 0.0),
        (11.0, 0.0, 0.0),
        (10.0, 1.0, 0.0),
    )
    triangles = ((0, 1, 2), (3, 4, 5))
    result = validate_mesh(vertices, triangles, prefer_trimesh=False)
    assert result.components == 2


def test_validation_rejects_bad_indices():
    _raises(
        ValueError,
        "out of range",
        lambda: validate_mesh(((0.0, 0.0, 0.0),) * 3, ((0, 1, 4),), prefer_trimesh=False),
    )


def test_vertex_clearance_is_translation_sensitive():
    _approx(nearest_target_clearance(((0.0, 0.0, 2.0),), ((0.0, 0.0, 0.0),)), 2.0)


def test_trimesh_surface_clearance_is_optional():
    vertices, triangles = square_mesh()
    try:
        distance = nearest_surface_clearance(((5.0, 5.0, 3.0),), vertices, triangles)
    except RuntimeError as exc:
        assert "trimesh" in str(exc)
    else:
        _approx(distance, 3.0)


def test_degenerate_face_is_reported_without_trimesh():
    result = validate_mesh(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        ((0, 1, 1),),
        prefer_trimesh=False,
    )
    assert result.degenerate_faces == 1


if __name__ == "__main__":
    for name, function in sorted(globals().items()):
        if name.startswith("test_"):
            function()
    print("mesh validation tests passed")
