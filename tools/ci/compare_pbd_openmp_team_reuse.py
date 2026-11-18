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
MIN_COLLISION_QUERY_IMPROVEMENT = 0.10
EXPERIMENT_ENVIRONMENT_KEY = "CLOTH_PBD_OPENMP_TEAM_REUSE"
COLLISION_QUERY_ENVIRONMENT_KEY = "CLOTH_PBD_COLLISION_QUERY_WORKERS"
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
    """Require one complete production audit with the expected experiment mode."""
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
    """Return fixed runner/OpenMP context, excluding one declared experiment toggle."""
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



def _mesh_collision_projector_total(profile: JsonObject, label: str) -> float:
    """Read the complete batched mesh-projector timing from one production profile."""
    stages = _as_object(
        profile.get("python_backend_stage_timings"),
        f"{label}.python_backend_stage_timings",
    )
    projector = _as_object(stages.get("mesh_collision_projector"), f"{label}.mesh_collision_projector")
    samples = _integer(projector.get("samples"), f"{label}.mesh_collision_projector.samples")
    if samples != EXPECTED_BACKEND_STEPS:
        raise ValueError(f"{label}: mesh collision projector timing sample count is incomplete")
    return _finite_number(
        projector.get("total_ms"), f"{label}.mesh_collision_projector.total_ms"
    )


def compare_collision_query_worker_profile_sets(
    baseline_profiles: list[JsonObject],
    candidate_profiles: list[JsonObject],
) -> JsonObject:
    """Require four complete matched audits and enforce query-stage and wall-time gates.

    Baseline uses one KDTree query worker; candidate uses four. Both keep the merged
    native OpenMP team-reuse path enabled and preserve exact nearest-neighbour search.
    """
    if len(baseline_profiles) != 2 or len(candidate_profiles) != 2:
        raise ValueError("exactly two one-worker and two four-worker profiles are required")

    records = [
        *((profile, "1", f"baseline-{index + 1}") for index, profile in enumerate(baseline_profiles)),
        *((profile, "4", f"candidate-{index + 1}") for index, profile in enumerate(candidate_profiles)),
    ]
    for profile, workers, label in records:
        _validate_profile(
            profile,
            workers,
            label,
            experiment_environment_key=COLLISION_QUERY_ENVIRONMENT_KEY,
            required_environment={"CLOTH_PBD_OPENMP_TEAM_REUSE": "1"},
        )

    reference = baseline_profiles[0]
    settings = reference.get("production_settings")
    groups = reference.get("native_constraint_groups")
    runtime = _runtime_signature(reference, COLLISION_QUERY_ENVIRONMENT_KEY)
    for profile, _, label in records[1:]:
        if profile.get("production_settings") != settings:
            raise ValueError(f"{label}: production settings differ from the matched baseline")
        if profile.get("native_constraint_groups") != groups:
            raise ValueError(
                f"{label}: native constraint grouping differs from the matched baseline"
            )
        if _runtime_signature(profile, COLLISION_QUERY_ENVIRONMENT_KEY) != runtime:
            raise ValueError(
                f"{label}: execution context differs (runner, OpenMP, or native build)"
            )

    baseline_projector = [
        _mesh_collision_projector_total(profile, f"baseline-{index + 1}")
        for index, profile in enumerate(baseline_profiles)
    ]
    candidate_projector = [
        _mesh_collision_projector_total(profile, f"candidate-{index + 1}")
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

    baseline_median_projector = median(baseline_projector)
    candidate_median_projector = median(candidate_projector)
    baseline_median_wall = median(baseline_wall)
    candidate_median_wall = median(candidate_wall)
    projector_improvement = 1.0 - candidate_median_projector / baseline_median_projector
    wall_time_change = candidate_median_wall / baseline_median_wall - 1.0

    rejection_reasons: list[str] = []
    if projector_improvement < MIN_COLLISION_QUERY_IMPROVEMENT:
        rejection_reasons.append(
            "four-worker mesh collision projector improvement is below 10%: "
            f"{projector_improvement * 100:.2f}%"
        )
    if wall_time_change > 0.0:
        rejection_reasons.append(
            "four-worker median production wall time regressed: "
            f"{wall_time_change * 100:.2f}%"
        )

    return {
        "schema_version": 1,
        "experiment": "pypbd-mesh-collision-kdtree-query-workers",
        "repetitions_per_mode": 2,
        "baseline_query_workers": 1,
        "candidate_query_workers": 4,
        "production_acceptance": "passed_all_four_runs",
        "baseline_mesh_collision_projector_total_ms": baseline_projector,
        "candidate_mesh_collision_projector_total_ms": candidate_projector,
        "baseline_median_mesh_collision_projector_ms": baseline_median_projector,
        "candidate_median_mesh_collision_projector_ms": candidate_median_projector,
        "mesh_collision_projector_improvement_fraction": projector_improvement,
        "mesh_collision_projector_improvement_percent": 100.0 * projector_improvement,
        "baseline_production_wall_ms": baseline_wall,
        "candidate_production_wall_ms": candidate_wall,
        "baseline_median_production_wall_ms": baseline_median_wall,
        "candidate_median_production_wall_ms": candidate_median_wall,
        "production_wall_time_change_fraction": wall_time_change,
        "production_wall_time_change_percent": 100.0 * wall_time_change,
        "acceptance": "rejected" if rejection_reasons else "passed",
        "rejection_reasons": rejection_reasons,
    }


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

    baseline_median_projection = median(baseline_projection)
    candidate_median_projection = median(candidate_projection)
    baseline_median_wall = median(baseline_wall)
    candidate_median_wall = median(candidate_wall)
    projection_improvement = 1.0 - candidate_median_projection / baseline_median_projection
    wall_time_change = candidate_median_wall / baseline_median_wall - 1.0

    rejection_reasons: list[str] = []
    if projection_improvement < MIN_PROJECTION_IMPROVEMENT:
        rejection_reasons.append(
            "persistent-team projection improvement is below 5%: "
            f"{projection_improvement * 100:.2f}%"
        )
    if wall_time_change > 0.0:
        rejection_reasons.append(
            f"persistent-team median production wall time regressed: {wall_time_change * 100:.2f}%"
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


def main() -> int:
    """Load the four production JSON profiles, compare them, and write the summary."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-1", type=Path, required=True)
    parser.add_argument("--baseline-2", type=Path, required=True)
    parser.add_argument("--candidate-1", type=Path, required=True)
    parser.add_argument("--candidate-2", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    paths = (args.baseline_1, args.baseline_2, args.candidate_1, args.candidate_2)
    profiles = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    if not all(isinstance(profile, dict) for profile in profiles):
        raise SystemExit("all experiment profiles must contain JSON objects")
    summary = compare_profile_sets([profiles[0], profiles[1]], [profiles[2], profiles[3]])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    status = str(summary["acceptance"])
    print(
        f"pypbd-openmp-team-reuse={status} "
        f"projection-improvement={summary['projection_improvement_percent']:.2f}% "
        f"production-wall-change={summary['production_wall_time_change_percent']:.2f}%",
        flush=True,
    )
    for reason in summary["rejection_reasons"]:
        print(f"rejection-reason={reason}", flush=True)
    return 0 if status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
