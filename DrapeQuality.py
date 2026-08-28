"""Headless quality metrics and benchmark helpers for cloth simulations.

This module deliberately observes ``ClothSystem`` state without changing solver
behaviour.  It is suitable for regression tests and CI benchmark reporting.
"""
from dataclasses import dataclass, asdict
from math import isfinite, sqrt
from time import perf_counter


@dataclass(frozen=True)
class DrapeMetrics:
    finite: bool
    max_position: float
    max_displacement: float
    max_constraint_error: float
    particle_count: int
    constraint_count: int
    stitch_count: int
    time: float

    def as_dict(self):
        return asdict(self)


def _distance(pa, pb):
    return sqrt(sum((pa[i] - pb[i]) ** 2 for i in range(3)))


def measure(system, initial_positions=None):
    """Return deterministic state/constraint metrics for a ``ClothSystem``."""
    positions = [p.position() for p in system.particles]
    finite = all(isfinite(v) for pos in positions for v in pos)
    max_position = max((max(abs(v) for v in pos) for pos in positions), default=0.0)
    if initial_positions is None:
        initial_positions = positions
    if len(initial_positions) != len(positions):
        raise ValueError("initial_positions length must match particle count")
    max_displacement = max(
        (_distance(a, b) for a, b in zip(initial_positions, positions)), default=0.0
    )
    constraints = list(system.constraints) + list(system.stitches)
    max_constraint_error = max(
        (abs(_distance(positions[c.a], positions[c.b]) - c.rest) for c in constraints),
        default=0.0,
    )
    return DrapeMetrics(
        finite=finite,
        max_position=max_position,
        max_displacement=max_displacement,
        max_constraint_error=max_constraint_error,
        particle_count=len(system.particles),
        constraint_count=len(system.constraints),
        stitch_count=len(system.stitches),
        time=float(system.time),
    )


def assert_quality(metrics, *, max_position=1e12, max_displacement=1e12,
                   max_constraint_error=1e-6):
    """Raise ``AssertionError`` when a run violates quality bounds."""
    assert metrics.finite, "cloth state contains non-finite coordinates"
    assert metrics.max_position <= max_position, "cloth position bound exceeded"
    assert metrics.max_displacement <= max_displacement, "cloth displacement bound exceeded"
    assert metrics.max_constraint_error <= max_constraint_error, "constraint residual bound exceeded"


def benchmark(factory, *, steps=30, dt=1.0 / 60.0, iterations=8, repeats=2, **step_kwargs):
    """Run a fixed simulation fixture repeatedly and return stable observations.

    ``factory`` must create a fresh system each repetition. Runtime is measured
    separately and therefore is intentionally excluded from determinism checks.
    """
    if steps < 1 or repeats < 1:
        raise ValueError("steps and repeats must be positive")
    runs = []
    for _ in range(repeats):
        system = factory()
        initial = [p.position() for p in system.particles]
        started = perf_counter()
        for _ in range(steps):
            system.step(dt=dt, iterations=iterations, **step_kwargs)
        elapsed = perf_counter() - started
        metrics = measure(system, initial)
        assert_quality(metrics)
        runs.append({"metrics": metrics.as_dict(), "runtime_seconds": elapsed,
                     "steps": steps, "dt": dt, "iterations": iterations})
    baseline = runs[0]["metrics"]
    for run in runs[1:]:
        assert run["metrics"] == baseline, "simulation metrics are not deterministic"
    return {"runs": runs, "metrics": baseline}
