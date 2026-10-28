# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression tests for cloth diagnostic metrics, validation, and deterministic export."""

import inspect
import math
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest

from freecad_cloth.simulation.ClothDiagnostics import (
    analyze_mesh,
    export_json,
    export_payload,
    fit_score,
    metric_definition,
    summarize,
)
from tests.support.assertions import require as _require

if TYPE_CHECKING:
    from collections.abc import Callable


def _triangle(scale: float = 1.0, z: float = 0.0) -> list[tuple[float, float, float]]:
    """Build a right-triangle mesh fixture in the XY plane.

    Args:
        scale: Uniform scale applied to both in-plane edge lengths.
        z: Constant height assigned to each vertex.

    Returns:
        Three vertices in counterclockwise boundary order.
    """
    return [(0.0, 0.0, z), (10.0 * scale, 0.0, z), (0.0, 10.0 * scale, z)]


def test_zero_deformation_is_zero_strain_and_full_fit() -> None:
    """Require zero strain and full fit when rest and current meshes match."""
    vertices = _triangle()
    result = analyze_mesh(vertices, vertices, [(0, 1, 2)], stretch_limit=0.02)
    _require(
        condition=result.strain == pytest.approx((0.0,)),
        message="Unchanged vertices must have zero strain.",
    )
    _require(
        condition=result.stress == pytest.approx((0.0,)),
        message="Unchanged vertices must have zero stress.",
    )
    _require(
        condition=result.fit == pytest.approx((1.0,)),
        message="An unchanged mesh must have full fit.",
    )
    _require(
        condition=result.pressure == pytest.approx((0.0,)),
        message="A mesh without pressure input must report zero pressure.",
    )


def test_stretch_is_normalized_against_fabric_limit() -> None:
    """Check that stretch and stress use the configured fabric limit."""
    rest = _triangle()
    current = _triangle(scale=1.1)
    result = analyze_mesh(rest, current, [(0, 1, 2)], stretch_limit=0.02)
    _require(
        condition=result.strain[0] == pytest.approx(0.1, rel=1e-9),
        message="Ten-percent stretch must be measured as 0.1 strain.",
    )
    _require(
        condition=result.stress[0] == pytest.approx(5.0, rel=1e-9),
        message="Stress must be normalized against the 0.02 stretch limit.",
    )

    degenerate_rest = ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    deformed = ((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0))
    degenerate_result = analyze_mesh(degenerate_rest, deformed, ((0, 1, 2),))
    _require(
        condition=degenerate_result.strain[0] == pytest.approx(math.sqrt(8.0) / 3.0),
        message="Zero-length edges must not hide strain from the other edges.",
    )


def test_fit_accepts_per_vertex_clearance() -> None:
    """Check that fit scoring consumes the per-vertex clearance values."""
    vertices = _triangle()
    result = analyze_mesh(
        vertices,
        vertices,
        [(0, 1, 2)],
        clearances=(0.0, 2.0, 4.0),
        fit_tolerance=6.0,
    )
    _require(
        condition=result.fit[0] == pytest.approx(2.0 / 3.0),
        message="Per-vertex clearances must contribute to the face fit score.",
    )


def test_fit_score_is_bounded_and_symmetric() -> None:
    """Check the fit score's bounds and symmetry about zero clearance."""
    _require(
        condition=math.isclose(fit_score(0.0, 5.0), 1.0, rel_tol=0.0, abs_tol=1e-12),
        message="Zero clearance must have a fit score of one.",
    )
    _require(
        condition=fit_score(2.5, 5.0) == pytest.approx(0.5),
        message="Half-tolerance positive clearance must score one half.",
    )
    _require(
        condition=fit_score(-2.5, 5.0) == pytest.approx(0.5),
        message="Fit scoring must be symmetric for negative clearance.",
    )
    _require(
        condition=math.isclose(fit_score(50.0, 5.0), 0.0, rel_tol=0.0, abs_tol=1e-12),
        message="Clearance beyond the supported range must have zero fit.",
    )


def test_pressure_length_must_match_faces() -> None:
    """Require a validation error when pressures do not match the face count."""
    vertices = _triangle()
    with pytest.raises(ValueError, match="pressures must be per-face"):
        analyze_mesh(vertices, vertices, [(0, 1, 2)], pressures=(1.0, 2.0))


def test_unknown_mesh_option_fails_closed() -> None:
    """Reject unsupported keyword names instead of silently ignoring caller typos."""
    runtime_analyze = cast("Callable[..., object]", analyze_mesh)
    with pytest.raises(
        TypeError,
        match=r"unexpected keyword argument 'stretch_limt'",
    ):
        runtime_analyze(
            _triangle(),
            _triangle(),
            ((0, 1, 2),),
            stretch_limt=0.02,
        )


def test_analyze_mesh_preserves_keyword_only_signature() -> None:
    """Keep the public mesh controls explicit for signature introspection."""
    parameters = inspect.signature(analyze_mesh).parameters
    expected_names = (
        "rest_vertices",
        "current_vertices",
        "triangles",
        "stretch_limit",
        "clearances",
        "fit_tolerance",
        "pressures",
    )
    option_defaults = {
        "stretch_limit": 0.02,
        "clearances": None,
        "fit_tolerance": 5.0,
        "pressures": None,
    }
    _require(
        condition=tuple(parameters) == expected_names,
        message="Mesh analysis must retain its explicit public parameters.",
    )
    _require(
        condition=all(
            parameters[name].kind is inspect.Parameter.KEYWORD_ONLY for name in option_defaults
        ),
        message="Optional mesh controls must remain keyword-only.",
    )
    _require(
        condition={name: parameters[name].default for name in option_defaults} == option_defaults,
        message="Mesh control defaults must remain stable for introspection.",
    )


def test_mesh_vertex_count_is_validated() -> None:
    """Require matching rest and current vertex counts."""
    with pytest.raises(ValueError, match="equal vertex counts"):
        analyze_mesh(_triangle(), _triangle()[:2], [(0, 1, 2)])


def test_summary_is_stable_for_export() -> None:
    """Check that mesh summary fields preserve pressure and stress metrics."""
    vertices = _triangle()
    result = analyze_mesh(vertices, _triangle(scale=1.02), [(0, 1, 2)], pressures=(12.0,))
    summary = summarize(result)
    _require(
        condition=summary["faces"] == 1,
        message="The summary must report the single input face.",
    )
    _require(
        condition=math.isclose(summary["pressure_max"], 12.0, rel_tol=0.0, abs_tol=1e-12),
        message="The summary must retain the maximum face pressure.",
    )
    _require(
        condition=summary["stress_max"] > 0,
        message="A stretched mesh must report positive maximum stress.",
    )


def test_metric_definition_is_explicit_and_stable() -> None:
    """Keep the stress formula and strain units explicit in the metric metadata."""
    _require(
        condition=metric_definition("stress")
        == {
            "formula": "|strain| / stretch_limit",
            "units": "normalized utilization",
        },
        message="Stress metadata must state its formula and normalized units.",
    )
    _require(
        condition=metric_definition("strain")["units"] == "dimensionless",
        message="Strain metadata must use dimensionless units.",
    )


def test_diagnostic_json_export_is_deterministic(tmp_path: Path) -> None:
    """Verify repeatable JSON output and the exported diagnostic schema.

    Args:
        tmp_path: Temporary directory supplied by pytest for export files.
    """
    vertices = _triangle()
    result = analyze_mesh(vertices, _triangle(scale=1.02), [(0, 1, 2)], pressures=(12.0,))
    payload = export_payload(result)
    first = tmp_path / "analysis.json"
    second = tmp_path / "analysis-second.json"
    export_json(result, first)
    export_json(result, second)
    _require(
        condition=first.read_text(encoding="utf-8") == second.read_text(encoding="utf-8"),
        message="Repeated exports of the same diagnostics must be byte-for-byte identical.",
    )
    _require(
        condition=payload["schema"] == 1,
        message="The exported diagnostics must use schema version one.",
    )
    _require(
        condition=payload["metrics"]["stress"] == pytest.approx(result.stress),
        message="The exported stress values must match the analyzed mesh.",
    )


def test_unknown_metric_definition_fails_closed() -> None:
    """Require unsupported metric names to raise a validation error."""
    with pytest.raises(ValueError, match="unknown diagnostic metric"):
        metric_definition("temperature")
