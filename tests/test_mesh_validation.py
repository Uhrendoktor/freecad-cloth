from freecad_cloth.common.MeshValidation import (
    measure_drape_visual_sanity,
    nearest_surface_clearance,
    nearest_target_clearance,
    summarize_drape_visual_metrics,
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


def test_drape_metrics_are_available_from_mesh_validation_boundary():
    target = ((-100.0, -50.0, 0.0), (100.0, -50.0, 0.0), (-100.0, 50.0, 1750.0), (100.0, 50.0, 1750.0))
    garment = ((-140.0, -90.0, 250.0), (140.0, -90.0, 250.0), (-140.0, 90.0, 1500.0), (140.0, 90.0, 1500.0))
    metrics = measure_drape_visual_sanity(garment, target, target_height=1750.0, target_width=1000.0)
    assert metrics.finite
    assert metrics.state == "structurally-plausible"
    assert metrics.vertices == 4
    assert metrics.bounds == (-140.0, 140.0, -90.0, 90.0, 250.0, 1500.0)
    assert metrics.vertical_span_ratio > 0.6
    assert metrics.lateral_span_ratio > 0.1
    data = summarize_drape_visual_metrics(metrics)
    assert data["state"] == metrics.state
    assert data["centroid"] == metrics.centroid


def test_drape_metrics_classify_empty_and_nonfinite_meshes():
    target = ((0.0, 0.0, 0.0),)
    assert measure_drape_visual_sanity((), target).state == "empty"
    nonfinite = measure_drape_visual_sanity(((0.0, 0.0, float("nan")),), target)
    assert nonfinite.state == "nonfinite"
    assert not nonfinite.finite


if __name__ == "__main__":
    for name, function in sorted(globals().items()):
        if name.startswith("test_"):
            function()
    print("mesh validation tests passed")
