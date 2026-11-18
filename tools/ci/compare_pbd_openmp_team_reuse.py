# Copyright (C) 2026 FreeCAD Cloth contributors
"""Compare matched production profiles for the opt-in pyPBD team-reuse experiment."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import median
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from freecad_cloth.common.JsonTypes import JsonObject, JsonValue

EXPECTED_SCENE_STEPS = 90
EXPECTED_BACKEND_STEPS = 360
EXPECTED_NATIVE_SUBSTEPS = 16
EXPECTED_POSITION_ITERATIONS = 8
MIN_PROJECTION_IMPROVEMENT = 0.05
MIN_STITCH_GROUP_CACHE_IMPROVEMENT = 0.10
EXPERIMENT_ENVIRONMENT_KEY = "CLOTH_PBD_OPENMP_TEAM_REUSE"
STITCH_GROUP_CACHE_ENVIRONMENT_KEY = "CLOTH_PBD_STITCH_GROUP_CACHE"
EXPERIMENT_MODULE_PREFIX = "/opt/pypbd-openmp-experiment/"
RUNTIME_CONTEXT_KEYS = (
    "cpu_model",
    "affinity_cpu_count",
    "affinity_cpus",
    "cgroup_cpu_max",
    "cgroup_cpu_quota_cores",
    "openmp_runtime_libraries",
    "pypbd_module",
    "platform",
    "machine",
    "simulation_backend_device",
)


def _as_object(value: JsonValue, label: str) -> JsonObject:
    """Require a JSON object at a named profile boundary."""
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _finite_number(value: JsonValue, label: str) -> float:
    """Require a finite, non-boolean, positive JSON number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{label} must be finite and positive")
    return result


def _integer(value: JsonValue, label: str) -> int:
    """Require a positive integer JSON metric."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _validate_profile(
    profile: JsonObject,
    expected_mode: str,
    label: str,
    *,
    experiment_environment_key: str = EXPERIMENT_ENVIRONMENT_KEY,
    required_environment: dict[str, str] | None = None,
) -> None:
    """Require one complete production audit with the expected native mode."""
    if profile.get("simulation_complete") is not True or profile.get("audit_complete") is not True:
        raise ValueError(f"{label}: production audit did not complete")
    if profile.get("acceptance_gates") != "passed":
        raise ValueError(f"{label}: production acceptance gates did not pass")
    if profile.get("scene_steps_requested") != EXPECTED_SCENE_STEPS:
        raise ValueError(f"{label}: requested scene-step count changed")
    if profile.get("scene_steps_completed") != EXPECTED_SCENE_STEPS:
        raise ValueError(f"{label}: scene-step count is incomplete")
    if profile.get("steps_requested") != EXPECTED_SCENE_STEPS:
        raise ValueError(f"{label}: requested step count changed")
    if profile.get("steps_completed") != EXPECTED_SCENE_STEPS:
        raise ValueError(f"{label}: completed-step count is incomplete")
    if profile.get("backend_steps_completed") != EXPECTED_BACKEND_STEPS:
        raise ValueError(f"{label}: backend-step count is incomplete")

    gates = _as_object(profile.get("acceptance_gate_results"), f"{label}.acceptance_gate_results")
    if len(gates) != 7 or any(value is not True for value in gates.values()):
        raise ValueError(f"{label}: all seven physical/visual gates must pass")

    settings = _as_object(profile.get("production_settings"), f"{label}.production_settings")
    expected_settings = {
        "particles": 1958,
        "collision_triangles": 26756,
        "collision_mode": "mesh",
        "scene_substeps": 4,
        "native_pbd_substeps": EXPECTED_NATIVE_SUBSTEPS,
        "position_iterations": EXPECTED_POSITION_ITERATIONS,
        "velocity_iterations": 8,
        "particle_distance_mm": 24.0,
        "time_step_seconds": 1.0 / 240.0,
        "collision_configured_tolerance_mm": 2.0,
        "collision_effective_clearance_mm": 5.0,
        "collision_thickness_mm": 5.0,
        "collision_voxel_mm": 8.0,
    }
    if any(settings.get(key) != value for key, value in expected_settings.items()):
        raise ValueError(f"{label}: production solver or collision settings changed")

    groups = _as_object(
        profile.get("native_constraint_groups"), f"{label}.native_constraint_groups"
    )
    if groups.get("constraint_count") != 9624 or groups.get("group_count") != 30:
        raise ValueError(f"{label}: native constraint-group distribution changed")

    timings = _as_object(
        profile.get("native_pypbd_stage_timings"),
        f"{label}.native_pypbd_stage_timings",
    )
    projection = _as_object(
        timings.get("position constraints projection"),
        f"{label}.position constraints projection",
    )
    expected_samples = EXPECTED_BACKEND_STEPS * EXPECTED_NATIVE_SUBSTEPS
    if _integer(projection.get("samples"), f"{label}.projection.samples") != expected_samples:
        raise ValueError(f"{label}: native projection timing sample count is incomplete")
    _finite_number(projection.get("total_ms"), f"{label}.projection.total_ms")
    _finite_number(profile.get("elapsed_production_ms"), f"{label}.elapsed_production_ms")

    runtime = _as_object(profile.get("runtime_limits"), f"{label}.runtime_limits")
    for key in RUNTIME_CONTEXT_KEYS:
        if key not in runtime:
            raise ValueError(f"{label}: missing runtime context {key}")
    module_path = runtime.get("pypbd_module")
    if not isinstance(module_path, str) or not module_path.startswith(EXPERIMENT_MODULE_PREFIX):
        raise ValueError(f"{label}: wrong pyPBD module path")

    thread_environment = _as_object(
        runtime.get("thread_environment"),
        f"{label}.runtime_limits.thread_environment",
    )
    if thread_environment.get(experiment_environment_key) != expected_mode:
        raise ValueError(f"{label}: unexpected {experiment_environment_key} mode")
    for key, value in (required_environment or {}).items():
        if thread_environment.get(key) != value:
            raise ValueError(f"{label}: {key} must remain {value} in every comparison run")

    provenance = profile.get("pypbd_provenance")
    if (
        not isinstance(provenance, str)
        or "10a70bc146a97873dc3c8fef372f5217e010542e" not in provenance
    ):
        raise ValueError(f"{label}: missing pinned native pyPBD provenance")
    if "Patch SHA256:" not in provenance or "Binary SHA256:" not in provenance:
        raise ValueError(f"{label}: native experiment binary provenance is incomplete")


def _runtime_signature(
    profile: JsonObject,
    experiment_environment_key: str = EXPERIMENT_ENVIRONMENT_KEY,
) -> tuple[JsonValue, ...]:
    """Return fixed runner/OpenMP context, excluding the intentional mode toggle."""
    runtime = _as_object(profile.get("runtime_limits"), "runtime_limits")
    environment = dict(
        _as_object(runtime.get("thread_environment"), "runtime_limits.thread_environment")
    )
    environment.pop(experiment_environment_key, None)
    context: list[JsonValue] = [runtime.get(key) for key in RUNTIME_CONTEXT_KEYS]
    context.extend((environment, profile.get("pypbd_provenance")))
    return tuple(context)


def _projection_total(profile: JsonObject, label: str) -> float:
    """Read the complete native projection total from one production profile."""
    timings = _as_object(
        profile.get("native_pypbd_stage_timings"),
        f"{label}.native_pypbd_stage_timings",
    )
    projection = _as_object(
        timings.get("position constraints projection"),
        f"{label}.position constraints projection",
    )
    return _finite_number(projection.get("total_ms"), f"{label}.projection.total_ms")


def _matched_timing_metrics(
    baseline_stage: list[float],
    candidate_stage: list[float],
    baseline_wall: list[float],
    candidate_wall: list[float],
    *,
    minimum_stage_improvement: float,
    stage_label: str,
    wall_regression_label: str,
) -> tuple[float, float, float, float, float, float, list[str]]:
    """Calculate matched median stage gains and enforce the production wall-time gate."""
    baseline_stage_median = median(baseline_stage)
    candidate_stage_median = median(candidate_stage)
    baseline_wall_median = median(baseline_wall)
    candidate_wall_median = median(candidate_wall)
    stage_improvement = 1.0 - candidate_stage_median / baseline_stage_median
    wall_time_change = candidate_wall_median / baseline_wall_median - 1.0
    rejection_reasons: list[str] = []
    if stage_improvement < minimum_stage_improvement:
        rejection_reasons.append(
            f"{stage_label} improvement is below {minimum_stage_improvement:.0%}: "
            f"{stage_improvement * 100:.2f}%"
        )
    if wall_time_change > 0.0:
        rejection_reasons.append(
            f"{wall_regression_label}: {wall_time_change * 100:.2f}%"
        )
    return (
        baseline_stage_median,
        candidate_stage_median,
        baseline_wall_median,
        candidate_wall_median,
        stage_improvement,
        wall_time_change,
        rejection_reasons,
    )


def compare_profile_sets(
    baseline_profiles: list[JsonObject],
    candidate_profiles: list[JsonObject],
) -> JsonObject:
    """Require two complete matched audits per mode and enforce both performance gates.

    Args:
        baseline_profiles: Two upstream per-group production profiles (mode 0).
        candidate_profiles: Two persistent-team production profiles (mode 1).

    Returns:
        A JSON-safe comparison summary.

    Raises:
        ValueError: If profiles are incomplete, contexts differ, or timing gates fail.
    """
    if len(baseline_profiles) != 2 or len(candidate_profiles) != 2:
        raise ValueError("exactly two baseline and two candidate profiles are required")

    records = [
        *(
            (profile, "0", f"baseline-{index + 1}")
            for index, profile in enumerate(baseline_profiles)
        ),
        *(
            (profile, "1", f"candidate-{index + 1}")
            for index, profile in enumerate(candidate_profiles)
        ),
    ]
    for profile, mode, label in records:
        _validate_profile(profile, mode, label)

    reference = baseline_profiles[0]
    settings = reference.get("production_settings")
    groups = reference.get("native_constraint_groups")
    runtime = _runtime_signature(reference)
    for profile, _, label in records[1:]:
        if profile.get("production_settings") != settings:
            raise ValueError(f"{label}: production settings differ from the matched baseline")
        if profile.get("native_constraint_groups") != groups:
            raise ValueError(
                f"{label}: native constraint grouping differs from the matched baseline"
            )
        if _runtime_signature(profile) != runtime:
            raise ValueError(
                f"{label}: execution context differs (runner, OpenMP, or native build)"
            )

    baseline_projection = [
        _projection_total(profile, f"baseline-{index + 1}")
        for index, profile in enumerate(baseline_profiles)
    ]
    candidate_projection = [
        _projection_total(profile, f"candidate-{index + 1}")
        for index, profile in enumerate(candidate_profiles)
    ]
    baseline_wall = [
        _finite_number(profile.get("elapsed_production_ms"), f"baseline-{i}.elapsed_production_ms")
        for i, profile in enumerate(baseline_profiles, 1)
    ]
    candidate_wall = [
        _finite_number(profile.get("elapsed_production_ms"), f"candidate-{i}.elapsed_production_ms")
        for i, profile in enumerate(candidate_profiles, 1)
    ]

    (
        baseline_median_projection,
        candidate_median_projection,
        baseline_median_wall,
        candidate_median_wall,
        projection_improvement,
        wall_time_change,
        rejection_reasons,
    ) = _matched_timing_metrics(
        baseline_projection,
        candidate_projection,
        baseline_wall,
        candidate_wall,
        minimum_stage_improvement=MIN_PROJECTION_IMPROVEMENT,
        stage_label="persistent-team projection",
        wall_regression_label="persistent-team median production wall time regressed",
    )

    return {
        "schema_version": 1,
        "experiment": "pypbd-openmp-persistent-team",
        "pinned_source": "10a70bc146a97873dc3c8fef372f5217e010542e",
        "repetitions_per_mode": 2,
        "production_acceptance": "passed_all_four_runs",
        "baseline_projection_total_ms": baseline_projection,
        "candidate_projection_total_ms": candidate_projection,
        "baseline_median_projection_total_ms": baseline_median_projection,
        "candidate_median_projection_total_ms": candidate_median_projection,
        "projection_improvement_fraction": projection_improvement,
        "projection_improvement_percent": 100.0 * projection_improvement,
        "baseline_production_wall_ms": baseline_wall,
        "candidate_production_wall_ms": candidate_wall,
        "baseline_median_production_wall_ms": baseline_median_wall,
        "candidate_median_production_wall_ms": candidate_median_wall,
        "production_wall_time_change_fraction": wall_time_change,
        "production_wall_time_change_percent": 100.0 * wall_time_change,
        "acceptance": "rejected" if rejection_reasons else "passed",
        "rejection_reasons": rejection_reasons,
    }



def _stitched_reconciliation_total(profile: JsonObject, label: str) -> float:
    """Read the complete per-step stitch-reconciliation stage timing."""
    stages = _as_object(
        profile.get("python_backend_stage_timings"),
        f"{label}.python_backend_stage_timings",
    )
    stitched = _as_object(
        stages.get("stitched_pair_reconciliation"),
        f"{label}.stitched_pair_reconciliation",
    )
    samples = _integer(stitched.get("samples"), f"{label}.stitched_pair_reconciliation.samples")
    if samples != EXPECTED_BACKEND_STEPS:
        raise ValueError(f"{label}: stitch-reconciliation timing sample count is incomplete")
    return _finite_number(
        stitched.get("total_ms"), f"{label}.stitched_pair_reconciliation.total_ms"
    )


def compare_stitch_group_cache_profile_sets(
    baseline_profiles: list[JsonObject],
    candidate_profiles: list[JsonObject],
) -> JsonObject:
    """Compare uncached versus cached stitch topology using four complete production audits."""
    if len(baseline_profiles) != 2 or len(candidate_profiles) != 2:
        raise ValueError("exactly two uncached and two cached profiles are required")

    records = [
        *((profile, "0", f"baseline-{index + 1}") for index, profile in enumerate(baseline_profiles)),
        *((profile, "1", f"candidate-{index + 1}") for index, profile in enumerate(candidate_profiles)),
    ]
    for profile, mode, label in records:
        _validate_profile(
            profile,
            mode,
            label,
            experiment_environment_key=STITCH_GROUP_CACHE_ENVIRONMENT_KEY,
            required_environment={EXPERIMENT_ENVIRONMENT_KEY: "1"},
        )

    reference = baseline_profiles[0]
    settings = reference.get("production_settings")
    groups = reference.get("native_constraint_groups")
    runtime = _runtime_signature(reference, STITCH_GROUP_CACHE_ENVIRONMENT_KEY)
    for profile, _, label in records[1:]:
        if profile.get("production_settings") != settings:
            raise ValueError(f"{label}: production settings differ from the matched baseline")
        if profile.get("native_constraint_groups") != groups:
            raise ValueError(
                f"{label}: native constraint grouping differs from the matched baseline"
            )
        if _runtime_signature(profile, STITCH_GROUP_CACHE_ENVIRONMENT_KEY) != runtime:
            raise ValueError(
                f"{label}: execution context differs (runner, OpenMP, or native build)"
            )

    baseline_stitched = [
        _stitched_reconciliation_total(profile, f"baseline-{index + 1}")
        for index, profile in enumerate(baseline_profiles)
    ]
    candidate_stitched = [
        _stitched_reconciliation_total(profile, f"candidate-{index + 1}")
        for index, profile in enumerate(candidate_profiles)
    ]
    baseline_wall = [
        _finite_number(profile.get("elapsed_production_ms"), f"baseline-{index + 1}.elapsed_production_ms")
        for index, profile in enumerate(baseline_profiles)
    ]
    candidate_wall = [
        _finite_number(profile.get("elapsed_production_ms"), f"candidate-{index + 1}.elapsed_production_ms")
        for index, profile in enumerate(candidate_profiles)
    ]
    (
        baseline_median_stitched,
        candidate_median_stitched,
        baseline_median_wall,
        candidate_median_wall,
        stitched_improvement,
        wall_time_change,
        rejection_reasons,
    ) = _matched_timing_metrics(
        baseline_stitched,
        candidate_stitched,
        baseline_wall,
        candidate_wall,
        minimum_stage_improvement=MIN_STITCH_GROUP_CACHE_IMPROVEMENT,
        stage_label="cached stitch-reconciliation",
        wall_regression_label="cached median production wall time regressed",
    )

    return {
        "schema_version": 1,
        "experiment": "pypbd-stitch-group-topology-cache",
        "repetitions_per_mode": 2,
        "baseline_stitch_group_cache": False,
        "candidate_stitch_group_cache": True,
        "production_acceptance": "passed_all_four_runs",
        "baseline_stitched_reconciliation_total_ms": baseline_stitched,
        "candidate_stitched_reconciliation_total_ms": candidate_stitched,
        "baseline_median_stitched_reconciliation_ms": baseline_median_stitched,
        "candidate_median_stitched_reconciliation_ms": candidate_median_stitched,
        "stitched_reconciliation_improvement_fraction": stitched_improvement,
        "stitched_reconciliation_improvement_percent": 100.0 * stitched_improvement,
        "baseline_production_wall_ms": baseline_wall,
        "candidate_production_wall_ms": candidate_wall,
        "baseline_median_production_wall_ms": baseline_median_wall,
        "candidate_median_production_wall_ms": candidate_median_wall,
        "production_wall_time_change_fraction": wall_time_change,
        "production_wall_time_change_percent": 100.0 * wall_time_change,
        "acceptance": "rejected" if rejection_reasons else "passed",
        "rejection_reasons": rejection_reasons,
    }

def main() -> int:
    """Load four production profiles and compare the selected PBD experiment."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-1", type=Path, required=True)
    parser.add_argument("--baseline-2", type=Path, required=True)
    parser.add_argument("--candidate-1", type=Path, required=True)
    parser.add_argument("--candidate-2", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--stitch-group-cache",
        action="store_true",
        help="Compare per-step stitch topology construction with cached components.",
    )
    args = parser.parse_args()

    paths = (args.baseline_1, args.baseline_2, args.candidate_1, args.candidate_2)
    profiles = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    if not all(isinstance(profile, dict) for profile in profiles):
        raise SystemExit("all experiment profiles must contain JSON objects")
    baseline = [profiles[0], profiles[1]]
    candidate = [profiles[2], profiles[3]]
    if args.stitch_group_cache:
        summary = compare_stitch_group_cache_profile_sets(baseline, candidate)
        experiment_name = "pypbd-stitch-group-cache"
        improvement_key = "stitched_reconciliation_improvement_percent"
        improvement_label = "stitch-stage-improvement"
    else:
        summary = compare_profile_sets(baseline, candidate)
        experiment_name = "pypbd-openmp-team-reuse"
        improvement_key = "projection_improvement_percent"
        improvement_label = "projection-improvement"

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\\n",
        encoding="utf-8",
    )
    status = str(summary["acceptance"])
    print(
        f"{experiment_name}={status} "
        f"{improvement_label}={summary[improvement_key]:.2f}% "
        f"production-wall-change={summary['production_wall_time_change_percent']:.2f}%",
        flush=True,
    )
    for reason in summary["rejection_reasons"]:
        print(f"rejection-reason={reason}", flush=True)
    return 0 if status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
