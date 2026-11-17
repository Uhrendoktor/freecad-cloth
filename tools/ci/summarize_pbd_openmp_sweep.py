# Copyright (C) 2026 FreeCAD Cloth contributors
"""Validate and summarize the matched production PBD OpenMP thread-count sweep."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import cast

type JsonValue = str | int | float | bool | list[JsonValue] | dict[str, JsonValue] | None

PROFILE_DIRECTORY = Path("artifacts/pbd-openmp-sweep")
PROFILE_FILES = {
    "unset": "unset.json",
    "omp-1": "omp-1.json",
    "omp-2": "omp-2.json",
    "omp-4": "omp-4.json",
}
EXPECTED_THREADS = {"unset": "unset", "omp-1": "1", "omp-2": "2", "omp-4": "4"}
EXPECTED_SETTINGS: dict[str, JsonValue] = {
    "particle_distance_mm": 24.0,
    "particles": 1958,
    "time_step_seconds": 0.004166666666666667,
    "scene_substeps": 4,
    "native_pbd_substeps": 16,
    "position_iterations": 8,
    "velocity_iterations": 8,
    "collision_mode": "mesh",
    "collision_triangles": 26756,
    "collision_thickness_mm": 5.0,
    "collision_voxel_mm": 8.0,
    "collision_configured_tolerance_mm": 2.0,
    "collision_effective_clearance_mm": 5.0,
}
HOST_FIELDS = (
    "platform",
    "machine",
    "logical_cpu_count",
    "cpu_model",
    "affinity_cpu_count",
    "affinity_cpus",
    "cgroup_cpu_max",
    "cgroup_cpu_quota_cores",
    "cgroup_cpuset",
    "pypbd_module",
    "openmp_runtime_libraries",
    "cuda_runner_probe",
    "cuda_runner_mode",
    "simulation_backend_device",
)
MINIMUM_PROJECTION_IMPROVEMENT_PERCENT = 5.0


def _mapping(value: JsonValue, label: str) -> dict[str, JsonValue]:
    """Return a JSON object or reject a malformed profile field."""
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return cast(dict[str, JsonValue], value)


def _field(mapping: dict[str, JsonValue], key: str, label: str) -> JsonValue:
    """Return one required JSON field."""
    if key not in mapping:
        raise ValueError(f"{label} is missing {key!r}")
    return mapping[key]


def _text(mapping: dict[str, JsonValue], key: str, label: str) -> str:
    """Return a required string field."""
    value = _field(mapping, key, label)
    if not isinstance(value, str):
        raise ValueError(f"{label}.{key} must be a string")
    return value


def _integer(mapping: dict[str, JsonValue], key: str, label: str) -> int:
    """Return a required integer field, excluding booleans."""
    value = _field(mapping, key, label)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label}.{key} must be an integer")
    return value


def _signed_number(mapping: dict[str, JsonValue], key: str, label: str) -> float:
    """Return a required finite numeric field, allowing negative deltas."""
    value = _field(mapping, key, label)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label}.{key} must be numeric")
    number = float(value)
    if not (-float("inf") < number < float("inf")):
        raise ValueError(f"{label}.{key} must be finite")
    return number


def _number(mapping: dict[str, JsonValue], key: str, label: str) -> float:
    """Return a required finite non-negative numeric field."""
    number = _signed_number(mapping, key, label)
    if number < 0.0:
        raise ValueError(f"{label}.{key} must be non-negative")
    return number


def _validate_profile(
    profile: dict[str, JsonValue],
    label: str,
) -> tuple[dict[str, JsonValue], dict[str, JsonValue], dict[str, JsonValue]]:
    """Validate completion, fixed physical settings, and runtime evidence."""
    if _integer(profile, "schema_version", label) != 1:
        raise ValueError(f"{label} has an unsupported profile schema")
    if _text(profile, "fixture", label) != "canonical-two-panel-tunic-production":
        raise ValueError(f"{label} is not the canonical production tunic fixture")
    if _field(profile, "simulation_complete", label) is not True:
        raise ValueError(f"{label} did not complete the production simulation")
    if _field(profile, "audit_complete", label) is not True:
        raise ValueError(f"{label} did not pass the complete production audit")
    for key in ("steps_requested", "scene_steps_requested"):
        if _integer(profile, key, label) != 90:
            raise ValueError(f"{label}.{key} is not the required 90-step workload")
    if _integer(profile, "scene_steps_completed", label) != 90:
        raise ValueError(f"{label} completed fewer than 90 scene steps")
    if _integer(profile, "backend_steps_completed", label) != 360:
        raise ValueError(f"{label} completed fewer than 360 backend calls")

    settings = _mapping(
        _field(profile, "production_settings", label),
        f"{label}.production_settings",
    )
    for key, expected in EXPECTED_SETTINGS.items():
        if _field(settings, key, f"{label}.production_settings") != expected:
            raise ValueError(
                f"{label} changed the required production setting {key}: "
                f"{settings.get(key)!r} != {expected!r}"
            )

    runtime = _mapping(_field(profile, "runtime_limits", label), f"{label}.runtime_limits")
    thread_environment = _mapping(
        _field(runtime, "thread_environment", f"{label}.runtime_limits"),
        f"{label}.runtime_limits.thread_environment",
    )
    expected_threads = EXPECTED_THREADS[label]
    if (
        _text(thread_environment, "OMP_NUM_THREADS", f"{label}.thread_environment")
        != expected_threads
    ):
        raise ValueError(f"{label} did not run with OMP_NUM_THREADS={expected_threads}")

    native_timings = _mapping(
        _field(profile, "native_pypbd_stage_timings", label),
        f"{label}.native_pypbd_stage_timings",
    )
    projection = _mapping(
        _field(native_timings, "position constraints projection", label),
        f"{label}.position constraints projection",
    )
    if _integer(projection, "samples", label) != 5760:
        raise ValueError(f"{label} has an unexpected native projection sample count")
    simulation_step = _mapping(
        _field(native_timings, "simulation step", label),
        f"{label}.simulation step",
    )
    if _integer(simulation_step, "samples", label) != 360:
        raise ValueError(f"{label} has an unexpected native simulation-step sample count")

    _number(profile, "elapsed_production_ms", label)
    _number(profile, "process_cpu_elapsed_ms", label)
    _number(projection, "total_ms", f"{label}.position constraints projection")
    if _number(profile, "elapsed_production_ms", label) <= 0.0:
        raise ValueError(f"{label} production elapsed time is zero")
    if _number(projection, "total_ms", f"{label}.position constraints projection") <= 0.0:
        raise ValueError(f"{label} native projection time is zero")
    return settings, runtime, thread_environment


def build_summary(profiles: dict[str, dict[str, JsonValue]]) -> dict[str, JsonValue]:
    """Compare four completed audits without changing their physical settings.

    The OpenMP hypothesis is actionable only when a candidate reduces native
    position-projection time by at least five percent and does not increase
    complete production elapsed time against the unset/default baseline.
    """
    if set(profiles) != set(PROFILE_FILES):
        raise ValueError(f"expected exactly these profile labels: {tuple(PROFILE_FILES)}")

    validated: dict[
        str,
        tuple[dict[str, JsonValue], dict[str, JsonValue], dict[str, JsonValue]],
    ] = {}
    for label in PROFILE_FILES:
        validated[label] = _validate_profile(profiles[label], label)

    baseline_settings, baseline_runtime, baseline_thread_environment = validated["unset"]
    baseline_projection = _number(
        _mapping(
            _mapping(profiles["unset"]["native_pypbd_stage_timings"], "unset.native timings")[
                "position constraints projection"
            ],
            "unset.position constraints projection",
        ),
        "total_ms",
        "unset.position constraints projection",
    )
    baseline_elapsed = _number(profiles["unset"], "elapsed_production_ms", "unset")

    host_context = {
        key: _field(baseline_runtime, key, "unset.runtime_limits") for key in HOST_FIELDS
    }
    baseline_other_thread_controls = {
        key: value for key, value in baseline_thread_environment.items() if key != "OMP_NUM_THREADS"
    }

    runs: dict[str, JsonValue] = {}
    comparisons: dict[str, JsonValue] = {}
    eligible: list[tuple[float, int]] = []
    for label in PROFILE_FILES:
        settings, runtime, thread_environment = validated[label]
        if settings != baseline_settings:
            raise ValueError(f"{label} does not use the exact baseline production settings")
        candidate_host = {
            key: _field(runtime, key, f"{label}.runtime_limits") for key in HOST_FIELDS
        }
        if candidate_host != host_context:
            raise ValueError(f"{label} ran on a different CPU/runtime context than the baseline")
        other_controls = {
            key: value for key, value in thread_environment.items() if key != "OMP_NUM_THREADS"
        }
        if other_controls != baseline_other_thread_controls:
            raise ValueError(f"{label} changed thread controls other than OMP_NUM_THREADS")

        native_timings = _mapping(
            profiles[label]["native_pypbd_stage_timings"],
            f"{label}.native timings",
        )
        projection = _mapping(
            native_timings["position constraints projection"],
            f"{label}.position constraints projection",
        )
        projection_ms = _number(projection, "total_ms", f"{label}.projection")
        elapsed_ms = _number(profiles[label], "elapsed_production_ms", label)
        process_cpu_ms = _number(profiles[label], "process_cpu_elapsed_ms", label)
        runs[label] = {
            "omp_num_threads": EXPECTED_THREADS[label],
            "elapsed_production_ms": elapsed_ms,
            "process_cpu_elapsed_ms": process_cpu_ms,
            "position_projection_total_ms": projection_ms,
            "position_projection_samples": _integer(projection, "samples", label),
        }
        if label == "unset":
            continue

        projection_improvement = 100.0 * (baseline_projection - projection_ms) / baseline_projection
        elapsed_change = 100.0 * (elapsed_ms - baseline_elapsed) / baseline_elapsed
        actionable = (
            projection_improvement >= MINIMUM_PROJECTION_IMPROVEMENT_PERCENT
            and elapsed_ms <= baseline_elapsed
        )
        comparisons[label] = {
            "projection_improvement_percent": projection_improvement,
            "production_elapsed_change_percent": elapsed_change,
            "actionable": actionable,
        }
        if actionable:
            eligible.append((projection_improvement, int(EXPECTED_THREADS[label])))

    selected_threads: int | None = None
    reason = (
        "No thread count reduced native position-constraint projection by at least "
        "5% without increasing full production elapsed time. Reject the OpenMP team-startup "
        "hypothesis. Do not change production thread defaults on this evidence; "
        "profile per-constraint arithmetic and group-size distributions next."
    )
    disposition = "openmp-thread-scaling-rejected"
    if eligible:
        _best_improvement, selected_threads = max(eligible, key=lambda item: item[0])
        disposition = "openmp-thread-scaling-actionable"
        reason = (
            f"OMP_NUM_THREADS={selected_threads} met both criteria: at least 5% lower "
            "native position-projection time and no increase in complete production elapsed time."
        )

    return {
        "schema_version": 1,
        "fixture": "canonical-two-panel-tunic-production",
        "baseline": "OMP_NUM_THREADS unset (runtime default)",
        "production_settings": baseline_settings,
        "runtime_context": host_context,
        "runs": runs,
        "candidate_comparisons": comparisons,
        "decision": {
            "disposition": disposition,
            "selected_thread_count": selected_threads,
            "minimum_projection_improvement_percent": MINIMUM_PROJECTION_IMPROVEMENT_PERCENT,
            "production_elapsed_must_not_increase": True,
            "reason": reason,
        },
    }


def _render_markdown(summary: dict[str, JsonValue]) -> str:
    """Render a compact human-readable experiment report."""
    runs = _mapping(summary["runs"], "summary.runs")
    comparisons = _mapping(summary["candidate_comparisons"], "summary.candidate_comparisons")
    decision = _mapping(summary["decision"], "summary.decision")
    lines = [
        "# Production PBD OpenMP thread-count sweep",
        "",
        "All rows represent the unchanged 90-step two-panel production tunic audit.",
        "The unset row is the default-runtime baseline; all candidates ran sequentially",
        "on the same hosted runner and pinned FreeCAD/pyPBD image.",
        "Positive projection percentages mean faster projection; negative values mean slower.",
        "Positive wall percentages mean a slower full audit; negative values mean faster.",
        "",
        "| OpenMP threads | Production wall (s) | Process CPU (s) | "
        "Native position projection (s) | Projection change | Wall change |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for label in PROFILE_FILES:
        run = _mapping(runs[label], f"summary.runs.{label}")
        thread_count = _text(run, "omp_num_threads", f"summary.runs.{label}")
        elapsed = _number(run, "elapsed_production_ms", label) / 1000.0
        cpu = _number(run, "process_cpu_elapsed_ms", label) / 1000.0
        projection = _number(run, "position_projection_total_ms", label) / 1000.0
        if label == "unset":
            projection_change = "baseline"
            wall_change = "baseline"
        else:
            comparison = _mapping(comparisons[label], f"summary.comparisons.{label}")
            projection_change = f"{_signed_number(comparison, 'projection_improvement_percent', label):+.2f}% improvement"
            wall_change = (
                f"{_signed_number(comparison, 'production_elapsed_change_percent', label):+.2f}%"
            )
        lines.append(
            f"| {thread_count} | {elapsed:.3f} | {cpu:.3f} | {projection:.3f} | "
            f"{projection_change} | {wall_change} |"
        )
    lines.extend(
        [
            "",
            f"**Disposition:** {_text(decision, 'disposition', 'summary.decision')}",
            "",
            _text(decision, "reason", "summary.decision"),
            "",
            "Physical settings and production acceptance thresholds were identical across runs.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    """Load the four saved profiles and write JSON/Markdown comparison artifacts."""
    try:
        profiles: dict[str, dict[str, JsonValue]] = {}
        for label, filename in PROFILE_FILES.items():
            loaded = cast(
                JsonValue,
                json.loads((PROFILE_DIRECTORY / filename).read_text(encoding="utf-8")),
            )
            profiles[label] = _mapping(loaded, str(PROFILE_DIRECTORY / filename))
        summary = build_summary(profiles)
        (PROFILE_DIRECTORY / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (PROFILE_DIRECTORY / "summary.md").write_text(_render_markdown(summary), encoding="utf-8")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        sys.stderr.write(f"pbd-openmp-sweep=invalid: {exc}\n")
        return 1

    decision = _mapping(summary["decision"], "summary.decision")
    sys.stdout.write(f"pbd-openmp-sweep={_text(decision, 'disposition', 'summary.decision')}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
