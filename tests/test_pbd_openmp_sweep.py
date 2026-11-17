# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression tests for the production PBD OpenMP sweep comparator."""

from __future__ import annotations

from typing import cast

import pytest

from tools.ci.summarize_pbd_openmp_sweep import (
    EXPECTED_SETTINGS,
    JsonValue,
    _render_markdown,
    build_summary,
)


def _profile(
    omp_threads: str,
    projection_ms: float,
    elapsed_ms: float,
) -> dict[str, JsonValue]:
    """Build one complete canonical tunic profile for comparator tests."""
    return {
        "schema_version": 1,
        "fixture": "canonical-two-panel-tunic-production",
        "simulation_complete": True,
        "audit_complete": True,
        "steps_requested": 90,
        "scene_steps_requested": 90,
        "scene_steps_completed": 90,
        "backend_steps_completed": 360,
        "elapsed_production_ms": elapsed_ms,
        "process_cpu_elapsed_ms": elapsed_ms * 3.0,
        "production_settings": dict(EXPECTED_SETTINGS),
        "native_pypbd_stage_timings": {
            "position constraints projection": {
                "samples": 5760,
                "total_ms": projection_ms,
            },
            "simulation step": {"samples": 360, "total_ms": projection_ms + 1000.0},
        },
        "runtime_limits": {
            "platform": "linux",
            "machine": "x86_64",
            "logical_cpu_count": 8,
            "cpu_model": "AMD EPYC 7763",
            "affinity_cpu_count": 4,
            "affinity_cpus": [0, 1, 2, 3],
            "cgroup_cpu_max": "max 100000",
            "cgroup_cpu_quota_cores": None,
            "cgroup_cpuset": "0-3",
            "pypbd_module": "/opt/freecad/pyPBD.cpython-312-x86_64-linux-gnu.so",
            "openmp_runtime_libraries": ["libgomp.so.1"],
            "cuda_runner_probe": False,
            "cuda_runner_mode": "cpu-fallback",
            "simulation_backend_device": "cpu",
            "thread_environment": {
                "OMP_NUM_THREADS": omp_threads,
                "OMP_DYNAMIC": "unset",
                "OMP_PROC_BIND": "unset",
                "OMP_PLACES": "unset",
                "OMP_MAX_ACTIVE_LEVELS": "unset",
                "OMP_THREAD_LIMIT": "unset",
                "OMP_WAIT_POLICY": "unset",
                "GOMP_SPINCOUNT": "unset",
                "OPENBLAS_NUM_THREADS": "unset",
                "MKL_NUM_THREADS": "unset",
                "NUMEXPR_NUM_THREADS": "unset",
            },
        },
    }


def _profiles(
    omp_1: tuple[float, float] = (9800.0, 19800.0),
    omp_2: tuple[float, float] = (9300.0, 19900.0),
    omp_4: tuple[float, float] = (9000.0, 20100.0),
) -> dict[str, dict[str, JsonValue]]:
    """Return baseline and three thread-count variants."""
    return {
        "unset": _profile("unset", 10000.0, 20000.0),
        "omp-1": _profile("1", *omp_1),
        "omp-2": _profile("2", *omp_2),
        "omp-4": _profile("4", *omp_4),
    }


def _decision(summary: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Return the decision record from a valid summary."""
    return cast(dict[str, JsonValue], summary["decision"])


def test_sweep_selects_projection_gain_without_wall_time_regression() -> None:
    """Select the best thread count that clears both performance criteria."""
    summary = build_summary(_profiles())
    decision = _decision(summary)

    assert decision["disposition"] == "openmp-thread-scaling-actionable"
    assert decision["selected_thread_count"] == 2


def test_markdown_renders_negative_performance_deltas() -> None:
    """Negative speedup and wall-time deltas are valid report values."""
    summary = build_summary(
        _profiles(
            omp_1=(11000.0, 21000.0),
            omp_2=(10300.0, 20500.0),
            omp_4=(9000.0, 20200.0),
        )
    )

    report = _render_markdown(summary)

    assert "-10.00% improvement" in report
    assert "+5.00%" in report
    assert "-3.00% improvement" in report
    assert "**Disposition:** openmp-thread-scaling-rejected" in report


def test_sweep_rejects_projection_gain_that_slows_the_full_audit() -> None:
    """A projection-only speedup is insufficient when total production time rises."""
    summary = build_summary(
        _profiles(
            omp_1=(9000.0, 20100.0),
            omp_2=(9200.0, 20200.0),
            omp_4=(9300.0, 20300.0),
        )
    )
    decision = _decision(summary)

    assert decision["disposition"] == "openmp-thread-scaling-rejected"
    assert decision["selected_thread_count"] is None


def test_sweep_rejects_gains_below_the_five_percent_threshold() -> None:
    """Small projection differences do not justify an OpenMP tuning change."""
    summary = build_summary(
        _profiles(
            omp_1=(9600.0, 19900.0),
            omp_2=(9550.0, 19900.0),
            omp_4=(9510.0, 19900.0),
        )
    )
    decision = _decision(summary)

    assert decision["disposition"] == "openmp-thread-scaling-rejected"


def test_sweep_rejects_incomplete_production_evidence() -> None:
    """Partial profiles and timed-out audits cannot be compared as passes."""
    profiles = _profiles()
    profiles["omp-2"]["audit_complete"] = False

    with pytest.raises(ValueError, match="complete production audit"):
        build_summary(profiles)


def test_sweep_rejects_wrong_thread_environment() -> None:
    """The profiler must confirm the requested OpenMP setting in each run."""
    profiles = _profiles()
    runtime = cast(dict[str, JsonValue], profiles["omp-4"]["runtime_limits"])
    environment = cast(dict[str, JsonValue], runtime["thread_environment"])
    environment["OMP_NUM_THREADS"] = "2"

    with pytest.raises(ValueError, match="did not run with OMP_NUM_THREADS=4"):
        build_summary(profiles)


def test_sweep_rejects_changed_physics_settings_or_runner_context() -> None:
    """Runs must retain the profile and execute on the same measured CPU context."""
    profiles = _profiles()
    settings = cast(dict[str, JsonValue], profiles["omp-1"]["production_settings"])
    settings["position_iterations"] = 4

    with pytest.raises(ValueError, match="changed the required production setting"):
        build_summary(profiles)

    profiles = _profiles()
    runtime = cast(dict[str, JsonValue], profiles["omp-1"]["runtime_limits"])
    runtime["cpu_model"] = "different runner"

    with pytest.raises(ValueError, match="different CPU/runtime context"):
        build_summary(profiles)
