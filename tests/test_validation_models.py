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
    NormalizedRange,
    RectangleDimensions,
    SeamAllowanceOptions,
    TriangulationOptions,
    validate_point2d,
    validate_points3d,
)
from freecad_cloth.pattern.PatternGeometry import LineSegment, rectangle
from freecad_cloth.sewing.SewingCorrespondence import (
    analyze_correspondence,
    arc_length_vertex_indices,
    correspondence_samples,
)


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
        validate_mesh(
            [[0, 0, 0], [1, 0, 0], [0, 1, 0]], [[0, 1.5, 2]], prefer_trimesh=False
        )


def test_coordinate_validation_rejects_wrong_dimensions_and_nan() -> None:
    with pytest.raises(ValidationError):
        MeshArrays.model_validate({"vertices": [[0, 0]], "triangles": []})
    with pytest.raises(ValidationError):
        validate_points3d([[1, 2, 3], [4, 5, math.nan]])


@pytest.mark.parametrize("count", [1, 2.5, True, "3"])
def test_arc_length_api_requires_an_exact_integer_count(count: object) -> None:
    with pytest.raises(ValueError):
        arc_length_vertex_indices(
            (1, 2, 3), ((0, 0), (1, 0), (2, 0)), count  # type: ignore[arg-type]
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
