"""Regression tests for numerical and geometry input schemas."""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from freecad_cloth.common.MeshValidation import nearest_target_clearance, validate_mesh
from freecad_cloth.common.ValidationModels import (
    ArcLengthSamplingInput,
    CorrespondenceAnalysisInput,
    MeshArrays,
    MeshHealthMetrics,
    NormalizedRange,
    PngCaptureMetrics,
    PngCaptureOptions,
    RectangleDimensions,
    SeamAllowanceOptions,
    TriangulationOptions,
    validate_point2d,
    validate_points3d,
)
from freecad_cloth.pattern.PatternGeometry import (
    LineSegment,
    PolylineSegment,
    QuadraticBezier,
    rectangle,
    seam_allowance_outline,
)
from freecad_cloth.pattern.PatternMesh import TriangleMesh
from freecad_cloth.sewing.SeamGraph import Transform3D
from freecad_cloth.sewing.SewingCorrespondence import (
    analyze_correspondence,
    arc_length_vertex_indices,
    correspondence_samples,
)
from freecad_cloth.simulation.ClothSolver import ClothSystem, DistanceConstraint, Particle


def test_mesh_schema_normalizes_coordinates_but_keeps_indices_exact() -> None:
    mesh = MeshArrays.model_validate(
        {"vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]], "triangles": [[0, 1, 2]]}
    )
    assert mesh.vertices == ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    assert mesh.triangles == ((0, 1, 2),)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, "1.0", True])
def test_point_schema_rejects_nonfinite_or_coerced_coordinates(value: object) -> None:
    with pytest.raises(ValidationError):
        validate_point2d((value, 0.0))


@pytest.mark.parametrize("face", [[0, 1.5, 2], [0, True, 2], [0, -1, 2], [0, 1, 3]])
def test_mesh_schema_rejects_invalid_face_indices(face: list[object]) -> None:
    with pytest.raises(ValidationError):
        MeshArrays.model_validate(
            {"vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]], "triangles": [face]}
        )


def test_mesh_api_rejects_fractional_indices_instead_of_truncating() -> None:
    with pytest.raises(ValueError):
        validate_mesh([[0, 0, 0], [1, 0, 0], [0, 1, 0]], [[0, 1.5, 2]], prefer_trimesh=False)


def test_coordinate_validation_rejects_wrong_dimensions_and_nan() -> None:
    with pytest.raises(ValidationError):
        MeshArrays.model_validate({"vertices": [[0, 0]], "triangles": []})
    with pytest.raises(ValidationError):
        validate_points3d([[1, 2, 3], [4, 5, math.nan]])


@pytest.mark.parametrize("count", [1, 2.5, True, "3"])
def test_arc_length_api_requires_an_exact_integer_count(count: object) -> None:
    with pytest.raises(ValueError):
        arc_length_vertex_indices(
            (1, 2, 3),
            ((0, 0), (1, 0), (2, 0)),
            count,  # type: ignore[arg-type]
        )
    with pytest.raises(ValidationError):
        ArcLengthSamplingInput.model_validate(
            {"values": [1, 2, 3], "points": [[0, 0], [1, 0], [2, 0]], "count": count}
        )


@pytest.mark.parametrize(
    ("start", "end"),
    [(math.nan, 1.0), (0.0, math.inf), (0.5, 0.5), (-0.1, 1.0), (0.0, 1.1)],
)
def test_normalized_range_rejects_nonfinite_empty_and_outside_intervals(
    start: float, end: float
) -> None:
    with pytest.raises(ValidationError):
        NormalizedRange(start=start, end=end)


def test_correspondence_schema_keeps_range_status_separate_from_numeric_validity() -> None:
    with pytest.raises(ValidationError):
        CorrespondenceAnalysisInput(length_a=math.nan, length_b=10.0)
    data = CorrespondenceAnalysisInput(length_a=10.0, length_b=10.0, start_a=0.8, end_a=0.2)
    assert (data.start_a, data.end_a) == (0.8, 0.2)
    report = analyze_correspondence(10.0, 10.0, start_a=0.8, end_a=0.2)
    assert report.status == "invalid_range"


def test_seam_parameter_sampling_rejects_invalid_options() -> None:
    with pytest.raises(ValueError):
        correspondence_samples(2.5)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        correspondence_samples(3, start_a=0.8, end_a=0.2)


def test_library_option_schemas_validate_numeric_knobs() -> None:
    with pytest.raises(ValidationError):
        RectangleDimensions(width=10.0, height=math.inf)
    with pytest.raises(ValidationError):
        SeamAllowanceOptions(allowance=-1.0, curve_samples=8)
    with pytest.raises(ValidationError):
        SeamAllowanceOptions(allowance=math.nan, curve_samples=8)
    with pytest.raises(ValidationError):
        TriangulationOptions(curve_samples=4.5, max_area=10.0)
    with pytest.raises(ValidationError):
        TriangulationOptions(curve_samples=16, max_area=math.inf)


def test_pattern_geometry_rejects_nonfinite_coordinates_and_dimensions() -> None:
    with pytest.raises(ValueError):
        LineSegment("bad", (0.0, math.nan), (1.0, 0.0))
    with pytest.raises(ValueError):
        rectangle(math.inf, 10.0)
    with pytest.raises(ValueError):
        rectangle(10.0, math.nan)
    with pytest.raises(ValueError):
        rectangle(10.0, 10.0).sampled_outline(2.5)


def test_vertex_clearance_uses_matching_3d_dimensions() -> None:
    assert nearest_target_clearance(((0.0, 0.0, 2.0),), ((0.0, 0.0, 0.0),)) == 2.0
    with pytest.raises(ValueError):
        nearest_target_clearance(((0.0, 0.0),), ((0.0, 0.0, 0.0),))


def test_fallback_components_do_not_merge_faces_touching_at_only_one_vertex() -> None:
    vertices = (
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (-1.0, 0.0, 0.0),
        (0.0, -1.0, 0.0),
    )
    result = validate_mesh(vertices, ((0, 1, 2), (0, 3, 4)), prefer_trimesh=False)
    assert result.components == 2


def test_triangle_mesh_rejects_out_of_range_boundary_indices() -> None:
    mesh = TriangleMesh(
        vertices=((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)),
        triangles=((0, 1, 2),),
        boundary_vertex_indices=(0, 1, 9),
    )
    with pytest.raises(ValueError, match="boundary"):
        mesh.validate()


def test_interpolation_avoids_overflow_for_finite_opposite_extremes() -> None:
    line = LineSegment("extreme-line", (-1e308, 0.0), (1e308, 0.0))
    assert line.point(0.5) == (0.0, 0.0)
    curve = QuadraticBezier("extreme-bezier", (-1e308, 0.0), (1e308, 0.0), (-1e308, 0.0))
    assert curve.point(0.5) == (0.0, 0.0)


def test_computed_polygon_area_overflow_fails_closed() -> None:
    pattern = rectangle(1e308, 1e308)
    with pytest.raises(ValueError, match="area must be finite"):
        seam_allowance_outline(pattern, 1.0)


def test_triangle_mesh_area_overflow_fails_closed() -> None:
    mesh = TriangleMesh(
        vertices=((0.0, 0.0), (1e308, 0.0), (0.0, 1e308)),
        triangles=((0, 1, 2),),
        boundary_vertex_indices=(0, 1, 2),
    )
    with pytest.raises(ValueError, match="area must be finite"):
        _ = mesh.area


def test_vertex_clearance_overflow_fails_closed() -> None:
    with pytest.raises(ValueError, match="clearance must be finite"):
        nearest_target_clearance(((-1e308, 0.0, 0.0),), ((1e308, 0.0, 0.0),))


@pytest.mark.parametrize(
    "particle",
    [
        (math.nan, 0.0, 0.0, 1.0),
        (0.0, math.inf, 0.0, 1.0),
        (0.0, 0.0, 0.0, math.nan),
        (0.0, 0.0, 0.0, -1.0),
    ],
)
def test_particle_rejects_nonfinite_state_and_negative_inverse_mass(
    particle: tuple[float, float, float, float],
) -> None:
    with pytest.raises(ValueError):
        Particle(*particle)


def test_solver_grid_validates_finite_dimensions_origin_and_integer_resolution() -> None:
    with pytest.raises(ValueError):
        ClothSystem.grid(math.nan, 10.0)
    with pytest.raises(ValueError):
        ClothSystem.grid(10.0, 10.0, nx=2.5)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        ClothSystem.grid(10.0, 10.0, origin=(0.0, math.inf, 0.0))


def test_solver_rejects_fractional_pin_and_stitch_indices() -> None:
    system = ClothSystem.grid(10.0, 10.0, nx=2, ny=2)
    with pytest.raises(ValueError):
        system.pin([0.5])  # type: ignore[list-item]
    with pytest.raises(ValueError):
        system.add_stitches([(0.5, 1)])  # type: ignore[list-item]


def test_distance_constraints_validate_fields_and_particle_references() -> None:
    with pytest.raises(ValueError):
        DistanceConstraint(0.5, 1, 0.0)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        DistanceConstraint(0, 1, math.nan)
    with pytest.raises(ValueError):
        DistanceConstraint(0, 1, 0.0, math.inf)
    system_particles = [Particle(0.0, 0.0, 0.0), Particle(1.0, 0.0, 0.0)]
    with pytest.raises(ValueError, match="outside system"):
        ClothSystem(system_particles, constraints=[DistanceConstraint(0, 2, 1.0)])


def test_transform_rejects_nonfinite_matrix_and_overflowing_result() -> None:
    matrix = list(Transform3D.identity().matrix)
    matrix[0] = math.nan
    with pytest.raises(ValueError):
        Transform3D(tuple(matrix))
    transform = Transform3D.translation(1e308, 0.0, 0.0)
    with pytest.raises(ValueError):
        transform.apply((1e308, 0.0, 0.0))


def test_polyline_interpolation_avoids_overflow_for_large_same_sign_points() -> None:
    segment = PolylineSegment("extreme-polyline", ((1e308, 0.0), (1.1e308, 0.0)))
    assert segment.point(0.5) == pytest.approx((1.05e308, 0.0))


def test_png_options_validate_dimensions_and_thresholds() -> None:
    assert PngCaptureOptions(expected_width=800).expected_width == 800
    assert PngCaptureOptions(expected_height=600).expected_height == 600
    with pytest.raises(ValidationError):
        PngCaptureOptions(pixel_threshold=257)
    with pytest.raises(ValidationError):
        PngCaptureOptions(minimum_pixels=-1)


def test_png_metrics_schema_rejects_impossible_counts_and_dimensions() -> None:
    with pytest.raises(ValidationError, match="opaque pixel count"):
        PngCaptureMetrics(width=1, height=1, opaque_pixels=2, nonwhite_pixels=1, distinct_rgb=1)
    with pytest.raises(ValidationError, match="visible pixel count"):
        PngCaptureMetrics(width=2, height=2, opaque_pixels=2, nonwhite_pixels=3, distinct_rgb=1)


def test_mesh_health_metrics_rejects_invalid_bounds_and_counts() -> None:
    with pytest.raises(ValidationError, match="ordered"):
        MeshHealthMetrics(
            vertices=3,
            faces=1,
            components=1,
            bounds=(1.0, 0.0, 0.0, 1.0, 0.0, 1.0),
            surface_area=0.5,
            watertight=False,
            finite=True,
            degenerate_faces=0,
        )
    with pytest.raises(ValidationError, match="component count"):
        MeshHealthMetrics(
            vertices=3,
            faces=1,
            components=2,
            bounds=(0.0, 1.0, 0.0, 1.0, 0.0, 1.0),
            surface_area=0.5,
            watertight=False,
            finite=True,
            degenerate_faces=0,
        )
