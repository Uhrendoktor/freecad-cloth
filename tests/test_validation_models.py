# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression tests for numerical and geometry input schemas."""

from __future__ import annotations

import math
from typing import cast

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
from tests.support.assertions import require


EXPECTED_CLEARANCE_MM = 2.0
EXPECTED_DISCONNECTED_COMPONENTS = 2
EXPECTED_PNG_WIDTH = 800
EXPECTED_PNG_HEIGHT = 600


def test_mesh_schema_normalizes_coordinates_but_keeps_indices_exact() -> None:
    """Normalize mesh coordinates while preserving exact integer connectivity."""
    mesh = MeshArrays.model_validate(
        {"vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]], "triangles": [[0, 1, 2]]}
    )
    require(condition=mesh.vertices == ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)), message="Mesh schema did not normalize vertex coordinates.")
    require(condition=mesh.triangles == ((0, 1, 2),), message="Mesh schema changed exact face indices.")


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, "1.0", True])
def test_point_schema_rejects_nonfinite_or_coerced_coordinates(value: object) -> None:
    """Reject non-finite and coerced coordinate values.

    Args:
        value: Invalid coordinate component supplied to the schema.
    """
    with pytest.raises(ValidationError):
        validate_point2d((value, 0.0))


@pytest.mark.parametrize("face", [[0, 1.5, 2], [0, True, 2], [0, -1, 2], [0, 1, 3]])
def test_mesh_schema_rejects_invalid_face_indices(face: list[object]) -> None:
    """Reject invalid face indices before they enter mesh geometry.

    Args:
        face: Triangle index list containing a malformed or out-of-range value.
    """
    with pytest.raises(ValidationError):
        MeshArrays.model_validate(
            {"vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]], "triangles": [face]}
        )


def test_mesh_api_rejects_fractional_indices_instead_of_truncating() -> None:
    """Reject fractional mesh indices instead of truncating them."""
    with pytest.raises(ValueError, match="valid integer"):
        validate_mesh(
            cast("list[tuple[float, float, float]]", [[0, 0, 0], [1, 0, 0], [0, 1, 0]]),
            cast("list[tuple[int, int, int]]", [[0, 1.5, 2]]),
            prefer_trimesh=False,
        )


def test_coordinate_validation_rejects_wrong_dimensions_and_nan() -> None:
    """Reject coordinate arrays with wrong dimensions or non-finite values."""
    with pytest.raises(ValidationError):
        MeshArrays.model_validate({"vertices": [[0, 0]], "triangles": []})
    with pytest.raises(ValidationError):
        validate_points3d([[1, 2, 3], [4, 5, math.nan]])


@pytest.mark.parametrize(
    ("count", "expected_error"),
    [
        (1, "greater than or equal"),
        (2.5, "valid integer"),
        (True, "valid integer"),
        ("3", "valid integer"),
    ],
)
def test_arc_length_api_requires_an_exact_integer_count(count: object, expected_error: str) -> None:
    """Reject sample counts that are not exact integers of at least two.

    Args:
        count: Invalid sample-count value passed to the API.
        expected_error: Validation diagnostic fragment expected for this invalid count.
    """
    with pytest.raises(ValueError, match=expected_error):
        arc_length_vertex_indices(
            (1, 2, 3),
            ((0, 0), (1, 0), (2, 0)),
            cast("int", count),
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
    """Reject normalized intervals that are non-finite, empty, or outside the unit range.

    Args:
        start: Candidate normalized interval start.
        end: Candidate normalized interval end.
    """
    with pytest.raises(ValidationError):
        NormalizedRange(start=start, end=end)


def test_correspondence_schema_keeps_range_status_separate_from_numeric_validity() -> None:
    """Keep invalid seam ranges distinct from invalid numeric inputs."""
    with pytest.raises(ValidationError):
        CorrespondenceAnalysisInput(length_a=math.nan, length_b=10.0)
    data = CorrespondenceAnalysisInput(length_a=10.0, length_b=10.0, start_a=0.8, end_a=0.2)
    require(condition=(data.start_a, data.end_a) == (0.8, 0.2), message="Schema normalization changed the invalid seam range.")
    report = analyze_correspondence(10.0, 10.0, start_a=0.8, end_a=0.2)
    require(condition=report.status == "invalid_range", message="Invalid seam ranges were not classified separately.")


def test_seam_parameter_sampling_rejects_invalid_options() -> None:
    """Reject invalid sample counts and reversed seam parameter ranges."""
    with pytest.raises(ValueError, match="valid integer"):
        correspondence_samples(cast("int", 2.5))
    with pytest.raises(ValueError, match="seam parameter ranges"):
        correspondence_samples(3, start_a=0.8, end_a=0.2)


def test_library_option_schemas_validate_numeric_knobs() -> None:
    """Validate the numeric settings shared by pattern and triangulation APIs."""
    with pytest.raises(ValidationError):
        RectangleDimensions(width=10.0, height=math.inf)
    with pytest.raises(ValidationError):
        SeamAllowanceOptions(allowance=-1.0, curve_samples=8)
    with pytest.raises(ValidationError):
        SeamAllowanceOptions(allowance=math.nan, curve_samples=8)
    with pytest.raises(ValidationError):
        TriangulationOptions(curve_samples=cast("int", 4.5), max_area=10.0)
    with pytest.raises(ValidationError):
        TriangulationOptions(curve_samples=16, max_area=math.inf)


def test_pattern_geometry_rejects_nonfinite_coordinates_and_dimensions() -> None:
    """Reject non-finite geometry and invalid curve-sampling counts."""
    with pytest.raises(ValueError, match="finite"):
        LineSegment("bad", (0.0, math.nan), (1.0, 0.0))
    with pytest.raises(ValueError, match="finite"):
        rectangle(math.inf, 10.0)
    with pytest.raises(ValueError, match="finite"):
        rectangle(10.0, math.nan)
    with pytest.raises(ValueError, match="valid integer"):
        rectangle(10.0, 10.0).sampled_outline(cast("int", 2.5))


def test_vertex_clearance_uses_matching_3d_dimensions() -> None:
    """Require matching three-dimensional points for clearance calculations."""
    require(condition=nearest_target_clearance(((0.0, 0.0, EXPECTED_CLEARANCE_MM),), ((0.0, 0.0, 0.0),)) == pytest.approx(EXPECTED_CLEARANCE_MM), message="Vertex clearance is not calculated in three dimensions.")
    with pytest.raises(ValueError, match="3 items"):
        nearest_target_clearance(
            cast("tuple[tuple[float, float, float], ...]", ((0.0, 0.0),)),
            ((0.0, 0.0, 0.0),),
        )


def test_fallback_components_do_not_merge_faces_touching_at_only_one_vertex() -> None:
    """Keep faces connected at only a vertex in separate components."""
    vertices = (
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (-1.0, 0.0, 0.0),
        (0.0, -1.0, 0.0),
    )
    result = validate_mesh(vertices, ((0, 1, 2), (0, 3, 4)), prefer_trimesh=False)
    require(condition=result.components == EXPECTED_DISCONNECTED_COMPONENTS, message="Faces that only share a vertex were merged into one component.")


def test_triangle_mesh_rejects_out_of_range_boundary_indices() -> None:
    """Reject boundary indices that point beyond existing mesh vertices."""
    mesh = TriangleMesh(
        vertices=((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)),
        triangles=((0, 1, 2),),
        boundary_vertex_indices=(0, 1, 9),
    )
    with pytest.raises(ValueError, match="boundary"):
        mesh.validate()


def test_interpolation_avoids_overflow_for_finite_opposite_extremes() -> None:
    """Interpolate opposite large finite endpoints without overflowing intermediate values."""
    line = LineSegment("extreme-line", (-1e308, 0.0), (1e308, 0.0))
    require(condition=line.point(0.5) == (0.0, 0.0), message="Line interpolation overflowed.")
    curve = QuadraticBezier("extreme-bezier", (-1e308, 0.0), (1e308, 0.0), (-1e308, 0.0))
    require(condition=curve.point(0.5) == (0.0, 0.0), message="Bezier interpolation overflowed.")


def test_computed_polygon_area_overflow_fails_closed() -> None:
    """Reject polygon outlines whose computed area overflows."""
    pattern = rectangle(1e308, 1e308)
    with pytest.raises(ValueError, match="area must be finite"):
        seam_allowance_outline(pattern, 1.0)


def test_triangle_mesh_area_overflow_fails_closed() -> None:
    """Reject mesh area calculations that overflow to a non-finite result."""
    mesh = TriangleMesh(
        vertices=((0.0, 0.0), (1e308, 0.0), (0.0, 1e308)),
        triangles=((0, 1, 2),),
        boundary_vertex_indices=(0, 1, 2),
    )
    with pytest.raises(ValueError, match="area must be finite"):
        _ = mesh.area


def test_vertex_clearance_overflow_fails_closed() -> None:
    """Reject vertex clearance calculations that overflow to a non-finite result."""
    with pytest.raises(ValueError, match="clearance must be finite"):
        nearest_target_clearance(((-1e308, 0.0, 0.0),), ((1e308, 0.0, 0.0),))


@pytest.mark.parametrize(
    ("particle", "expected_error"),
    [
        ((math.nan, 0.0, 0.0, 1.0), "finite real number"),
        ((0.0, math.inf, 0.0, 1.0), "finite real number"),
        ((0.0, 0.0, 0.0, math.nan), "finite real number"),
        ((0.0, 0.0, 0.0, -1.0), "non-negative"),
    ],
)
def test_particle_rejects_nonfinite_state_and_negative_inverse_mass(
    particle: tuple[float, float, float, float], expected_error: str
) -> None:
    """Reject non-finite particle state and negative inverse mass.

    Args:
        particle: Particle position and inverse-mass fields under test.
        expected_error: Validation diagnostic fragment expected for the invalid particle.
    """
    with pytest.raises(ValueError, match=expected_error):
        Particle(*particle)


def test_solver_grid_validates_finite_dimensions_origin_and_integer_resolution() -> None:
    """Validate finite grid dimensions, origin, and exact resolution counts."""
    with pytest.raises(ValueError, match="finite"):
        ClothSystem.grid(math.nan, 10.0)
    with pytest.raises(ValueError, match="valid integer"):
        ClothSystem.grid(10.0, 10.0, nx=cast("int", 2.5))
    with pytest.raises(ValueError, match="finite"):
        ClothSystem.grid(10.0, 10.0, origin=(0.0, math.inf, 0.0))


def test_solver_rejects_fractional_pin_and_stitch_indices() -> None:
    """Reject fractional indices in pinning and seam-stitch operations."""
    system = ClothSystem.grid(10.0, 10.0, nx=2, ny=2)
    with pytest.raises(ValueError, match="integer"):
        system.pin(cast("list[int]", [0.5]))
    with pytest.raises(ValueError, match="integer"):
        system.add_stitches(cast("list[tuple[int, int]]", [(0.5, 1)]))


def test_distance_constraints_validate_fields_and_particle_references() -> None:
    """Validate constraint fields and every referenced particle index."""
    with pytest.raises(ValueError, match="valid integer"):
        DistanceConstraint(cast("int", 0.5), 1, 0.0)
    with pytest.raises(ValueError, match="finite real number"):
        DistanceConstraint(0, 1, math.nan)
    with pytest.raises(ValueError, match="finite real number"):
        DistanceConstraint(0, 1, 0.0, math.inf)
    system_particles = [Particle(0.0, 0.0, 0.0), Particle(1.0, 0.0, 0.0)]
    with pytest.raises(ValueError, match="outside system"):
        ClothSystem(system_particles, constraints=[DistanceConstraint(0, 2, 1.0)])


def test_transform_rejects_nonfinite_matrix_and_overflowing_result() -> None:
    """Reject non-finite transforms and overflow in transformed points."""
    matrix = list(Transform3D.identity().matrix)
    matrix[0] = math.nan
    with pytest.raises(ValueError, match="finite real number"):
        Transform3D(tuple(matrix))
    transform = Transform3D.translation(1e308, 0.0, 0.0)
    with pytest.raises(ValueError, match="finite"):
        transform.apply((1e308, 0.0, 0.0))


def test_polyline_interpolation_avoids_overflow_for_large_same_sign_points() -> None:
    """Preserve accurate interpolation for large same-sign coordinates."""
    segment = PolylineSegment("extreme-polyline", ((1e308, 0.0), (1.1e308, 0.0)))
    require(condition=segment.point(0.5) == pytest.approx((1.05e308, 0.0)), message="Large finite polyline interpolation lost precision.")


def test_png_options_validate_dimensions_and_thresholds() -> None:
    """Accept valid PNG dimensions and reject invalid capture thresholds."""
    require(condition=PngCaptureOptions(expected_width=EXPECTED_PNG_WIDTH).expected_width == EXPECTED_PNG_WIDTH, message="PNG capture width was not preserved.")
    require(condition=PngCaptureOptions(expected_height=EXPECTED_PNG_HEIGHT).expected_height == EXPECTED_PNG_HEIGHT, message="PNG capture height was not preserved.")
    with pytest.raises(ValidationError):
        PngCaptureOptions(pixel_threshold=257)
    with pytest.raises(ValidationError):
        PngCaptureOptions(minimum_pixels=-1)


def test_png_metrics_schema_rejects_impossible_counts_and_dimensions() -> None:
    """Reject PNG metrics with impossible pixel counts or dimensions."""
    with pytest.raises(ValidationError, match="opaque pixel count"):
        PngCaptureMetrics(width=1, height=1, opaque_pixels=2, nonwhite_pixels=1, distinct_rgb=1)
    with pytest.raises(ValidationError, match="visible pixel count"):
        PngCaptureMetrics(width=2, height=2, opaque_pixels=2, nonwhite_pixels=3, distinct_rgb=1)


def test_mesh_health_metrics_rejects_invalid_bounds_and_counts() -> None:
    """Reject mesh-health metrics with unordered bounds or inconsistent components."""
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
