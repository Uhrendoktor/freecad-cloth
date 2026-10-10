import pytest

from freecad_cloth.common.MeshValidation import (
    nearest_surface_clearance,
    nearest_target_clearance,
    nearest_target_observation,
    validate_mesh,
)


def square_mesh():
    vertices = (
        (0.0, 0.0, 0.0),
        (10.0, 0.0, 0.0),
        (10.0, 10.0, 0.0),
        (0.0, 10.0, 0.0),
    )
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
    assert result.surface_area == pytest.approx(100.0)
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
    with pytest.raises(ValueError, match="out of range"):
        validate_mesh(((0.0, 0.0, 0.0),) * 3, ((0, 1, 4),), prefer_trimesh=False)


def test_vertex_clearance_is_translation_sensitive():
    assert nearest_target_clearance(((0.0, 0.0, 2.0),), ((0.0, 0.0, 0.0),)) == pytest.approx(
        2.0, abs=1e-9, rel=0.0
    )


def test_large_vertex_clearance_returns_exact_nearest_distance():
    """The required spatial index preserves the exact nearest-point distance."""
    garment = tuple((float(index), 5.0, 0.0) for index in range(48))
    target = tuple((float(index), 0.0, 0.0) for index in range(48))
    assert nearest_target_clearance(garment, target) == pytest.approx(5.0, abs=1e-9, rel=0.0)


def test_trimesh_surface_clearance_is_optional():
    vertices, triangles = square_mesh()
    try:
        distance = nearest_surface_clearance(((5.0, 5.0, 3.0),), vertices, triangles)
    except RuntimeError as exc:
        assert "trimesh" in str(exc)
    else:
        assert distance == pytest.approx(3.0, abs=1e-9, rel=0.0)


def test_degenerate_face_is_reported_without_trimesh():
    result = validate_mesh(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        ((0, 1, 1),),
        prefer_trimesh=False,
    )
    assert result.degenerate_faces == 1


def test_nearest_target_observation_returns_the_matching_target_vertex():
    source = ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0))
    target = ((3.0, 0.0, 0.0), (10.0, 1.0, 0.0))
    assert nearest_target_observation(source, target) == (1.0, (10.0, 1.0, 0.0))
    assert nearest_target_observation((), target) is None
