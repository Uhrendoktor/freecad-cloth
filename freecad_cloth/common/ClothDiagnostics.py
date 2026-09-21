"""Solver-neutral post-simulation diagnostics for the Cloth workbenches.

The diagnostics layer consumes rest/current mesh data and optional material/target
measurements. It never advances or modifies the solver and can therefore be used
by GUI, export, or headless validation code.
"""
from dataclasses import dataclass
import json
from math import isfinite, sqrt
from pathlib import Path
from typing import Sequence, Tuple

Point3 = Tuple[float, float, float]
Triangle = Tuple[int, int, int]

METRIC_DEFINITIONS = {
    "strain": {
        "label": "Strain",
        "units": "dimensionless fraction (×100 = %)",
        "formula": "epsilon = average(L_current / L_rest - 1)",
    },
    "stress": {
        "label": "Stress utilization",
        "units": "x allowable stretch (normalized)",
        "formula": "utilization = abs(strain) / stretch_limit",
    },
    "fit": {
        "label": "Fit",
        "units": "0–1 score",
        "formula": "fit = max(0, 1 - abs(clearance - ideal) / tolerance)",
    },
    "pressure": {
        "label": "Pressure",
        "units": "solver pressure units",
        "formula": "pressure = solver-provided per-face pressure",
    },
}


def metric_definition(name: str) -> dict:
    try:
        return dict(METRIC_DEFINITIONS[str(name)])
    except KeyError as exc:
        raise ValueError("unknown diagnostic metric: %s" % name) from exc


@dataclass(frozen=True)
class DiagnosticResult:
    """Per-face diagnostic values plus aggregate ranges."""

    strain: Tuple[float, ...]
    stress: Tuple[float, ...]
    fit: Tuple[float, ...]
    pressure: Tuple[float, ...]
    minimum: float
    maximum: float

    def metric(self, name: str) -> Tuple[float, ...]:
        try:
            values = getattr(self, str(name))
        except AttributeError as exc:
            raise ValueError("unknown diagnostic metric: %s" % name) from exc
        metric_definition(name)
        return values


def _distance(a: Point3, b: Point3) -> float:
    return sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def _triangle_edges(vertices: Sequence[Point3], tri: Triangle):
    a, b, c = (vertices[int(i)] for i in tri)
    return _distance(a, b), _distance(b, c), _distance(c, a)


def _safe_strain(current: float, rest: float) -> float:
    if rest <= 1e-12:
        return 0.0
    return current / rest - 1.0


def _average_edge_strain(rest_vertices, current_vertices, tri: Triangle) -> float:
    rest = _triangle_edges(rest_vertices, tri)
    current = _triangle_edges(current_vertices, tri)
    return sum(_safe_strain(c, r) for r, c in zip(rest, current)) / 3.0


def fit_score(clearance: float, tolerance: float, ideal: float = 0.0) -> float:
    """Return a 0..1 fit score from target clearance.

    A score of 1 means the measured clearance equals ``ideal``; it falls
    linearly to zero at ``tolerance``. This intentionally avoids assuming a
    particular avatar representation: callers supply the target measurement.
    """
    clearance = float(clearance)
    tolerance = abs(float(tolerance))
    ideal = float(ideal)
    if not all(isfinite(value) for value in (clearance, tolerance, ideal)):
        raise ValueError("fit inputs must be finite")
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
    """
    if len(rest_vertices) != len(current_vertices):
        raise ValueError("rest and current meshes must have equal vertex counts")
    if not triangles:
        return DiagnosticResult(
            strain=(),
            stress=(),
            fit=(),
            pressure=(),
            minimum=0.0,
            maximum=0.0,
        )
    for vertex_index, point in enumerate(rest_vertices):
        if len(point) != 3 or not all(isfinite(float(value)) for value in point):
            raise ValueError("rest vertex %d is non-finite" % vertex_index)
    for vertex_index, point in enumerate(current_vertices):
        if len(point) != 3 or not all(isfinite(float(value)) for value in point):
            raise ValueError("current vertex %d is non-finite" % vertex_index)
    vertex_count = len(current_vertices)
    for face_index, tri in enumerate(triangles):
        if len(tri) != 3 or any(not isinstance(index, int) or index < 0 or index >= vertex_count for index in tri):
            raise ValueError("triangle %d has invalid vertex indices" % face_index)
    stretch_limit = float(stretch_limit)
    if not isfinite(stretch_limit) or stretch_limit <= 0:
        raise ValueError("stretch_limit must be positive and finite")
    if fit_tolerance <= 0 or not isfinite(float(fit_tolerance)):
        raise ValueError("fit_tolerance must be positive and finite")
    if clearances is not None and len(clearances) not in (len(triangles), len(current_vertices)):
        raise ValueError("clearances must be per-face or per-vertex")
    if clearances is not None and not all(isfinite(float(value)) for value in clearances):
        raise ValueError("clearances must be finite")
    if pressures is not None and len(pressures) != len(triangles):
        raise ValueError("pressures must be per-face")
    if pressures is not None and not all(isfinite(float(value)) for value in pressures):
        raise ValueError("pressures must be finite")

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
    pressure = tuple(float(value) for value in pressures) if pressures is not None else tuple(0.0 for _ in triangles)
    values = strain + stress + fit + pressure
    return DiagnosticResult(
        strain=strain,
        stress=stress,
        fit=fit,
        pressure=pressure,
        minimum=min(values) if values else 0.0,
        maximum=max(values) if values else 0.0,
    )


def summarize(result: DiagnosticResult) -> dict:
    """Return a compact UI/export summary for a diagnostic result."""
    return {
        "faces": len(result.strain),
        "strain_min": min(result.strain) if result.strain else 0.0,
        "strain_max": max(result.strain) if result.strain else 0.0,
        "stress_max": max(result.stress) if result.stress else 0.0,
        "fit_min": min(result.fit) if result.fit else 1.0,
        "pressure_max": max(result.pressure) if result.pressure else 0.0,
    }


def export_analysis_data(result: DiagnosticResult, metric: str | None = None) -> str:
    """Return canonical, deterministic JSON for a diagnostic result.

    Export reads only the immutable DiagnosticResult. It never touches or mutates
    a FreeCAD document, simulation object, solver backend, or map object.
    """
    names = (str(metric),) if metric is not None else tuple(METRIC_DEFINITIONS)
    metrics = {}
    for name in names:
        definition = metric_definition(name)
        values = tuple(float(value) for value in result.metric(name))
        metrics[name] = {
            "formula": definition["formula"],
            "label": definition["label"],
            "maximum": max(values) if values else 0.0,
            "minimum": min(values) if values else 0.0,
            "units": definition["units"],
            "values": list(values),
        }
    payload = {
        "format": "freecad-cloth-diagnostic/v1",
        "metrics": metrics,
        "result_range": {
            "maximum": float(result.maximum),
            "minimum": float(result.minimum),
        },
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def write_analysis_data(path, result: DiagnosticResult, metric: str | None = None) -> None:
    """Write canonical diagnostic JSON without mutating any model state."""
    Path(path).write_text(export_analysis_data(result, metric) + "\n", encoding="utf-8")
