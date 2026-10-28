# Copyright (C) 2026 FreeCAD Cloth contributors
"""Solver-neutral post-simulation diagnostics for the Cloth workbenches.

The diagnostics layer consumes rest/current mesh data and optional material/target
measurements. It never advances or modifies the solver and can therefore be used
by GUI, export, or headless validation code.
"""

import json
import pathlib
from collections.abc import Sequence
from typing import TypedDict

import numpy as np
from numpy.typing import NDArray
from pydantic.dataclasses import dataclass as pydantic_dataclass

Point3 = tuple[float, float, float]
Triangle = tuple[int, int, int]


class DiagnosticMetricPayload(TypedDict):
    """Describe the per-face arrays in an exported diagnostic payload."""

    fit: list[float]
    pressure: list[float]
    strain: list[float]
    stress: list[float]


class DiagnosticRangePayload(TypedDict):
    """Describe the global extrema recorded by diagnostic export."""

    minimum: float
    maximum: float


class DiagnosticPayload(TypedDict):
    """Describe the stable JSON schema emitted by diagnostic export."""

    schema: int
    faces: int
    metrics: DiagnosticMetricPayload
    range: DiagnosticRangePayload
    summary: dict[str, int | float]


DIAGNOSTIC_EPSILON = 1e-12

METRIC_DEFINITIONS = {
    "strain": {"formula": "ΔL / L₀", "units": "dimensionless"},
    "stress": {"formula": "|strain| / stretch_limit", "units": "normalized utilization"},
    "fit": {"formula": "1 - |clearance - ideal| / tolerance", "units": "score 0..1"},
    "pressure": {"formula": "solver-provided per-face pressure", "units": "backend-native"},
}


def metric_definition(name: str) -> dict[str, str]:
    """Return the formula and units defined for one diagnostic metric.

    Args:
        name: Name of the metric whose definition is requested.

    Returns:
        A copy of the metric's formula and unit labels.

    Raises:
        ValueError: If the requested metric name is not recognized.
    """
    key = str(name).strip().lower()
    try:
        return dict(METRIC_DEFINITIONS[key])
    except KeyError as exc:
        msg = f"unknown diagnostic metric: {name}"
        raise ValueError(msg) from exc


def export_payload(result: "DiagnosticResult") -> DiagnosticPayload:
    """Build the JSON-ready payload for a completed diagnostics result.

    Args:
        result: Per-face metrics and global ranges produced by mesh analysis.

    Returns:
        A deterministic dictionary containing metric arrays, ranges, and a summary.

    Raises:
        TypeError: If the supplied value is not a DiagnosticResult.
    """
    if not isinstance(result, DiagnosticResult):
        msg = "result must be a DiagnosticResult"
        raise TypeError(msg)
    return {
        "schema": 1,
        "faces": len(result.strain),
        "metrics": {
            "fit": list(result.fit),
            "pressure": list(result.pressure),
            "strain": list(result.strain),
            "stress": list(result.stress),
        },
        "range": {"minimum": result.minimum, "maximum": result.maximum},
        "summary": summarize(result),
    }


def export_json(result: "DiagnosticResult", path: str | pathlib.Path) -> DiagnosticPayload:
    """Write the diagnostic payload as stable, formatted JSON.

    Args:
        result: Per-face metrics and global ranges to export.
        path: Destination filename or path-like object for the JSON document.

    Returns:
        The same JSON-ready payload written to the destination.
    """
    payload = export_payload(result)
    content = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    pathlib.Path(str(path)).write_text(content, encoding="utf-8", newline="")
    return payload


@pydantic_dataclass(frozen=True)
class DiagnosticResult:
    """Per-face diagnostic values plus aggregate ranges."""

    strain: tuple[float, ...]
    stress: tuple[float, ...]
    fit: tuple[float, ...]
    pressure: tuple[float, ...]
    minimum: float
    maximum: float

    def metric(self, name: str) -> tuple[float, ...]:
        """Get one per-face metric array by name.

        Args:
            name: Metric attribute to retrieve, such as strain or pressure.

        Returns:
            Values for the requested metric in face order.

        Raises:
            ValueError: If the name does not identify a metric on this result.
        """
        try:
            return getattr(self, str(name))
        except AttributeError as exc:
            msg = f"unknown diagnostic metric: {name}"
            raise ValueError(msg) from exc


def _average_edge_strains(
    rest_vertices: NDArray[np.float64],
    current_vertices: NDArray[np.float64],
    faces: NDArray[np.intp],
) -> NDArray[np.float64]:
    """Compute mean safe edge strain for all faces in one NumPy operation.

    Args:
        rest_vertices: Reference coordinates with shape (N, 3).
        current_vertices: Evaluated coordinates with shape (N, 3).
        faces: Triangle vertex indices with shape (M, 3).

    Returns:
        One mean relative edge-length change per face. Degenerate rest edges
        contribute zero strain, matching the scalar diagnostic contract.
    """
    if not faces.size:
        return np.empty(0, dtype=np.float64)

    rest_points = rest_vertices[faces]
    current_points = current_vertices[faces]
    rest_edges = np.stack(
        (
            rest_points[:, 1] - rest_points[:, 0],
            rest_points[:, 2] - rest_points[:, 1],
            rest_points[:, 0] - rest_points[:, 2],
        ),
        axis=1,
    )
    current_edges = np.stack(
        (
            current_points[:, 1] - current_points[:, 0],
            current_points[:, 2] - current_points[:, 1],
            current_points[:, 0] - current_points[:, 2],
        ),
        axis=1,
    )
    rest_lengths = np.linalg.norm(rest_edges, axis=2)
    current_lengths = np.linalg.norm(current_edges, axis=2)
    valid_edges = rest_lengths > DIAGNOSTIC_EPSILON
    edge_strains = np.zeros_like(rest_lengths, dtype=np.float64)
    np.divide(current_lengths, rest_lengths, out=edge_strains, where=valid_edges)
    edge_strains[valid_edges] -= 1.0
    return np.mean(edge_strains, axis=1, dtype=np.float64)


def _fit_score_array(
    clearances: NDArray[np.float64],
    tolerance: float,
    ideal: float = 0.0,
) -> NDArray[np.float64]:
    """Compute normalized fit scores for an array of clearances.

    Args:
        clearances: Per-face or per-vertex clearance values.
        tolerance: Absolute distance over which the score falls to zero.
        ideal: Clearance value representing a perfect fit.

    Returns:
        Fit scores in [0, 1], with the same shape as the input array.
    """
    tolerance = abs(float(tolerance))
    errors = np.abs(clearances - float(ideal))
    if tolerance <= DIAGNOSTIC_EPSILON:
        return (errors <= DIAGNOSTIC_EPSILON).astype(np.float64)
    return np.clip(1.0 - errors / tolerance, 0.0, 1.0)


def fit_score(clearance: float, tolerance: float, ideal: float = 0.0) -> float:
    """Return a 0..1 fit score from target clearance.

    A score of 1 means the measured clearance equals ``ideal``; it falls
    linearly to zero at ``tolerance``. This intentionally avoids assuming a
    particular avatar representation: callers supply the target measurement.

    Args:
        clearance: Measured distance between the simulated cloth and the target surface.
        tolerance: Absolute distance over which the score falls to zero.
        ideal: Clearance value that represents the best possible fit score.

    Returns:
        A normalized fit score between zero and one, inclusive.
    """
    values = np.asarray([float(clearance)], dtype=np.float64)
    return float(_fit_score_array(values, tolerance, ideal)[0])


def _mesh_arrays(
    rest_vertices: Sequence[Point3],
    current_vertices: Sequence[Point3],
    triangles: Sequence[Triangle],
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.intp]]:
    """Convert input mesh sequences to shaped NumPy arrays.

    Args:
        rest_vertices: Reference vertex coordinates before simulation.
        current_vertices: Vertex coordinates from the evaluated cloth mesh.
        triangles: Faces expressed as triples of vertex indices.

    Returns:
        Reference vertices, evaluated vertices, and indexed triangle arrays.
    """
    rest_array = np.asarray(rest_vertices, dtype=np.float64).reshape((-1, 3))
    current_array = np.asarray(current_vertices, dtype=np.float64).reshape((-1, 3))
    face_indices = np.asarray(triangles, dtype=np.intp).reshape((-1, 3))
    return rest_array, current_array, face_indices


def _fit_values(
    clearances: Sequence[float] | None,
    fit_tolerance: float,
    face_indices: NDArray[np.intp],
) -> NDArray[np.float64]:
    """Calculate a normalized fit score for each triangle.

    Args:
        clearances: Optional clearance values supplied per face or per vertex.
        fit_tolerance: Absolute distance over which the score falls to zero.
        face_indices: Triangle vertex indices with shape (M, 3).

    Returns:
        One bounded fit score per triangle.
    """
    if clearances is None:
        return np.ones(len(face_indices), dtype=np.float64)
    clearance_values = np.asarray(clearances, dtype=np.float64)
    face_clearances = (
        clearance_values
        if len(clearances) == len(face_indices)
        else np.mean(clearance_values[face_indices], axis=1, dtype=np.float64)
    )
    return _fit_score_array(face_clearances, fit_tolerance)


def _build_diagnostic_result(
    strain_values: NDArray[np.float64],
    stress_values: NDArray[np.float64],
    fit_values: NDArray[np.float64],
    pressure_values: NDArray[np.float64],
) -> DiagnosticResult:
    """Build immutable metric tuples and global extrema from computed arrays.

    Args:
        strain_values: Per-face relative edge-length change values.
        stress_values: Per-face strain utilization relative to the fabric limit.
        fit_values: Per-face normalized fit scores.
        pressure_values: Per-face solver-provided pressure values.

    Returns:
        Immutable diagnostic metrics and their combined minimum and maximum.
    """
    all_values = np.concatenate((strain_values, stress_values, fit_values, pressure_values))
    return DiagnosticResult(
        strain=tuple(float(value) for value in strain_values),
        stress=tuple(float(value) for value in stress_values),
        fit=tuple(float(value) for value in fit_values),
        pressure=tuple(float(value) for value in pressure_values),
        minimum=float(np.min(all_values)) if all_values.size else 0.0,
        maximum=float(np.max(all_values)) if all_values.size else 0.0,
    )


def analyze_mesh(
    rest_vertices: Sequence[Point3],
    current_vertices: Sequence[Point3],
    triangles: Sequence[Triangle],
    *,
    stretch_limit: float = 0.02,
    clearances: Sequence[float] | None = None,
    fit_tolerance: float = 5.0,
    pressures: Sequence[float] | None = None,
) -> DiagnosticResult:
    """Compute deterministic strain/stress/fit/pressure maps per triangle.

    ``stretch_limit`` is the fabric's authored allowable stretch. Stress is
    represented as normalized utilization (absolute strain / limit), which is
    solver-independent and safe to compare across materials.

    Args:
        rest_vertices: Reference vertex coordinates before simulation.
        current_vertices: Vertex coordinates from the evaluated cloth mesh.
        triangles: Faces expressed as triples of vertex indices.
        stretch_limit: Positive allowable relative edge stretch for the fabric.
        clearances: Optional per-face or per-vertex distance to a target surface.
        fit_tolerance: Absolute target-distance error at which fit reaches zero.
        pressures: Optional solver-provided pressure value for each face.

    Returns:
        Per-face strain, stress, fit and pressure metrics with global extrema.

    Raises:
        TypeError: If an unsupported keyword control is supplied.
        ValueError: If vertex counts differ, the stretch limit is nonpositive,
            or optional clearance and pressure arrays have unsupported lengths.
    """
    if len(rest_vertices) != len(current_vertices):
        msg = "rest and current meshes must have equal vertex counts"
        raise ValueError(msg)
    if stretch_limit <= 0:
        msg = "stretch_limit must be positive"
        raise ValueError(msg)
    if clearances is not None and len(clearances) not in {len(triangles), len(current_vertices)}:
        msg = "clearances must be per-face or per-vertex"
        raise ValueError(msg)
    if pressures is not None and len(pressures) != len(triangles):
        msg = "pressures must be per-face"
        raise ValueError(msg)

    rest_array, current_array, face_indices = _mesh_arrays(
        rest_vertices, current_vertices, triangles
    )
    strain_values = _average_edge_strains(rest_array, current_array, face_indices)
    stress_values = np.abs(strain_values) / float(stretch_limit)
    fit_values = _fit_values(clearances, fit_tolerance, face_indices)
    pressure_values = (
        np.asarray(pressures, dtype=np.float64)
        if pressures is not None
        else np.zeros(len(face_indices), dtype=np.float64)
    )
    return _build_diagnostic_result(
        strain_values, stress_values, fit_values, pressure_values
    )


def summarize(result: DiagnosticResult) -> dict[str, int | float]:
    """Summarize aggregate face counts and diagnostic extrema.

    Args:
        result: Per-face metric arrays and global ranges to summarize.

    Returns:
        A compact mapping of the face count and metric minimum/maximum values.
    """
    return {
        "faces": len(result.strain),
        "strain_min": min(result.strain) if result.strain else 0.0,
        "strain_max": max(result.strain) if result.strain else 0.0,
        "stress_max": max(result.stress) if result.stress else 0.0,
        "fit_min": min(result.fit) if result.fit else 1.0,
        "pressure_max": max(result.pressure) if result.pressure else 0.0,
    }
