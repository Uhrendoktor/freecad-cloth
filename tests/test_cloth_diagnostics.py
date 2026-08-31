import math

import pytest

from ClothDiagnostics import analyze_mesh, fit_score, summarize


def _triangle(scale=1.0, z=0.0):
    return [(0.0, 0.0, z), (10.0 * scale, 0.0, z), (0.0, 10.0 * scale, z)]


def test_zero_deformation_is_zero_strain_and_full_fit():
    vertices = _triangle()
    result = analyze_mesh(vertices, vertices, [(0, 1, 2)], stretch_limit=0.02)
    assert result.strain == pytest.approx((0.0,))
    assert result.stress == pytest.approx((0.0,))
    assert result.fit == pytest.approx((1.0,))
    assert result.pressure == pytest.approx((0.0,))


def test_stretch_is_normalized_against_fabric_limit():
    rest = _triangle()
    current = _triangle(scale=1.1)
    result = analyze_mesh(rest, current, [(0, 1, 2)], stretch_limit=0.02)
    assert result.strain[0] == pytest.approx(0.1, rel=1e-9)
    assert result.stress[0] == pytest.approx(5.0, rel=1e-9)


def test_fit_accepts_per_vertex_clearance():
    vertices = _triangle()
    result = analyze_mesh(
        vertices,
        vertices,
        [(0, 1, 2)],
        clearances=(0.0, 2.0, 4.0),
        fit_tolerance=6.0,
    )
    assert result.fit[0] == pytest.approx(2.0 / 3.0)


def test_fit_score_is_bounded_and_symmetric():
    assert fit_score(0.0, 5.0) == 1.0
    assert fit_score(2.5, 5.0) == pytest.approx(0.5)
    assert fit_score(-2.5, 5.0) == pytest.approx(0.5)
    assert fit_score(50.0, 5.0) == 0.0


def test_pressure_length_must_match_faces():
    vertices = _triangle()
    with pytest.raises(ValueError, match="pressures must be per-face"):
        analyze_mesh(vertices, vertices, [(0, 1, 2)], pressures=(1.0, 2.0))


def test_mesh_vertex_count_is_validated():
    with pytest.raises(ValueError, match="equal vertex counts"):
        analyze_mesh(_triangle(), _triangle()[:2], [(0, 1, 2)])


def test_summary_is_stable_for_export():
    vertices = _triangle()
    result = analyze_mesh(vertices, _triangle(scale=1.02), [(0, 1, 2)], pressures=(12.0,))
    summary = summarize(result)
    assert summary["faces"] == 1
    assert math.isclose(summary["pressure_max"], 12.0)
    assert summary["stress_max"] > 0
