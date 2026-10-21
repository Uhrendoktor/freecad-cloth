# Copyright (C) 2026 FreeCAD Cloth contributors
"""Solver-neutral post-simulation diagnostics for the Cloth workbenches.

The diagnostics layer consumes rest/current mesh data and optional material/target
measurements. It never advances or modifies the solver and can therefore be used
by GUI, export, or headless validation code.
"""

import pathlib
from collections.abc import Sequence
from math import sqrt

from pydantic.dataclasses import dataclass as pydantic_dataclass

Point3 = tuple[float, float, float]
Triangle = tuple[int, int, int]

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


def export_payload(result: "DiagnosticResult") -> dict[str, object]:
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


def export_json(result: "DiagnosticResult", path: str | pathlib.Path) -> dict[str, object]:
    """Write the diagnostic payload as stable, formatted JSON.

    Args:
        result: Per-face metrics and global ranges to export.
        path: Destination filename or path-like object for the JSON document.

    Returns:
        The same JSON-ready payload written to the destination.
    """
    import json

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


def _distance(a: Point3, b: Point3) -> float:
    """Measure the Euclidean distance between two 3D points.

    Args:
        a: First point in the mesh coordinate frame.
        b: Second point in the same coordinate frame.

    Returns:
        Straight-line distance between the supplied points.
    """
    return sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b, strict=False)))


def _triangle_edges(vertices: Sequence[Point3], tri: Triangle) -> tuple[float, float, float]:
    """Measure the three edge lengths of one triangular face.

    Args:
        vertices: Mesh vertex coordinates addressed by triangle indices.
        tri: Three indices defining the face.

    Returns:
        Edge lengths in AB, BC, and CA order.
    """
    a, b, c = (vertices[int(i)] for i in tri)
    return _distance(a, b), _distance(b, c), _distance(c, a)


def _safe_strain(current: float, rest: float) -> float:
    """Compute signed relative edge-length change with a zero-length guard.

    Args:
        current: Measured edge length after simulation.
        rest: Reference edge length before simulation.

    Returns:
        Relative length change, or zero when the reference edge is degenerate.
    """
    if rest <= 1e-12:
        return 0.0
    return current / rest - 1.0


def _average_edge_strain(
    rest_vertices: Sequence[Point3],
    current_vertices: Sequence[Point3],
    tri: Triangle,
) -> float:
    """Average safe relative edge strain across one triangular face.

    Args:
        rest_vertices: Reference mesh coordinates indexed by the triangle vertices.
        current_vertices: Current mesh coordinates with the same indexing as the reference.
        tri: Three vertex indices that define the face being measured.

    Returns:
        Mean of the three relative edge-length changes computed by the safe strain helper.
    """
    rest = _triangle_edges(rest_vertices, tri)
    current = _triangle_edges(current_vertices, tri)
    return sum(_safe_strain(c, r) for r, c in zip(rest, current, strict=False)) / 3.0


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
    tolerance = abs(float(tolerance))
    if tolerance <= 1e-12:
        return 1.0 if abs(float(clearance) - float(ideal)) <= 1e-12 else 0.0
    error = abs(float(clearance) - float(ideal))
    return max(0.0, min(1.0, 1.0 - error / tolerance))


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
        stretch_limit: Positive allowable fabric stretch used to normalize stress.
        clearances: Optional target clearances, supplied per face or per vertex.
        fit_tolerance: Distance scale over which a clearance fit score reaches zero.
        pressures: Optional solver-provided pressure values, one per face.

    Returns:
        Per-face strain, stress, fit and pressure metrics with global extrema.

    Raises:
        ValueError: If mesh vertex counts differ, the stretch limit is nonpositive,
            or optional clearance and pressure arrays have unsupported lengths.
    """
    if len(rest_vertices) != len(current_vertices):
        msg = "rest and current meshes must have equal vertex counts"
        raise ValueError(msg)
    if stretch_limit <= 0:
        msg = "stretch_limit must be positive"
        raise ValueError(msg)
    if clearances is not None and len(clearances) not in (len(triangles), len(current_vertices)):
        msg = "clearances must be per-face or per-vertex"
        raise ValueError(msg)
    if pressures is not None and len(pressures) != len(triangles):
        msg = "pressures must be per-face"
        raise ValueError(msg)

    strain = tuple(_average_edge_strain(rest_vertices, current_vertices, tri) for tri in triangles)
    stress = tuple(abs(value) / float(stretch_limit) for value in strain)
    if clearances is None:
        fit = tuple(1.0 for _ in triangles)
    elif len(clearances) == len(triangles):
        fit = tuple(fit_score(value, fit_tolerance) for value in clearances)
    else:
        fit = tuple(
            fit_score(sum(float(clearances[int(i)]) for i in tri) / 3.0, fit_tolerance)
            for tri in triangles
        )
    pressure = (
        tuple(float(value) for value in pressures)
        if pressures is not None
        else tuple(0.0 for _ in triangles)
    )
    values = strain + stress + fit + pressure
    return DiagnosticResult(
        strain=strain,
        stress=stress,
        fit=fit,
        pressure=pressure,
        minimum=min(values) if values else 0.0,
        maximum=max(values) if values else 0.0,
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
