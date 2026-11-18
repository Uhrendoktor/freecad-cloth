# Copyright (C) 2026 FreeCAD Cloth contributors
"""Tests for the matched production pyPBD OpenMP team-reuse comparator."""

from __future__ import annotations

from copy import deepcopy

import pytest

from freecad_cloth.common.JsonTypes import JsonObject
from tools.ci.compare_pbd_openmp_team_reuse import (
    compare_collision_query_worker_profile_sets,
    compare_profile_sets,
)


def _profile(
    mode: str,
    *,
    projection_ms: float = 11000.0,
    wall_ms: float = 20300.0,
) -> JsonObject:
    """Build one complete, context-pinned production audit profile."""
    return {
        "simulation_complete": True,
        "audit_complete": True,
        "acceptance_gates": "passed",
        "scene_steps_requested": 90,
        "scene_steps_completed": 90,
        "steps_requested": 90,
        "steps_completed": 90,
        "backend_steps_completed": 360,
        "acceptance_gate_results": {
            "finite_90_step_state": True,
            "seam_overlay": True,
            "panel_mesh_nonempty": True,
            "authoritative_seam_correspondence": True,
            "target_clearance_and_penetration": True,
            "six_view_visual_capture": True,
            "drape_visual_diagnostics": True,
        },
        "production_settings": {
            "particles": 1958,
            "collision_triangles": 26756,
            "collision_mode": "mesh",
            "scene_substeps": 4,
            "native_pbd_substeps": 16,
            "position_iterations": 8,
            "velocity_iterations": 8,
            "particle_distance_mm": 24.0,
            "time_step_seconds": 1.0 / 240.0,
            "collision_configured_tolerance_mm": 2.0,
            "collision_effective_clearance_mm": 5.0,
            "collision_thickness_mm": 5.0,
            "collision_voxel_mm": 8.0,
        },
        "native_constraint_groups": {
            "constraint_count": 9624,
            "group_count": 30,
            "openmp_parallel_threshold": 64,
            "parallel_eligible_group_count": 26,
        },
        "native_pypbd_stage_timings": {
            "position constraints projection": {
                "samples": 5760,
                "total_ms": projection_ms,
            }
        },
        "elapsed_production_ms": wall_ms,
        "runtime_limits": {
            "cpu_model": "AMD EPYC 9V74 80-Core Processor",
            "affinity_cpu_count": 4,
            "affinity_cpus": [0, 1, 2, 3],
            "cgroup_cpu_max": "max 100000",
            "cgroup_cpu_quota_cores": None,
            "openmp_runtime_libraries": ["libgomp.so.1"],
            "pypbd_module": "/opt/pypbd-openmp-experiment/pypbd.cpython-312-x86_64-linux-gnu.so",
            "platform": "linux",
            "machine": "x86_64",
            "simulation_backend_device": "cpu",
            "thread_environment": {
                "OMP_NUM_THREADS": "unset",
                "OMP_DYNAMIC": "unset",
                "OMP_PROC_BIND": "unset",
                "OMP_WAIT_POLICY": "unset",
                "CLOTH_PBD_OPENMP_TEAM_REUSE": mode,
            },
        },
        "pypbd_provenance": (
            "PBD source: 10a70bc146a97873dc3c8fef372f5217e010542e\n"
            "Patch SHA256: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n"
            "Binary SHA256: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n"
        ),
    }


def _matched_profiles() -> tuple[list[JsonObject], list[JsonObject]]:
    """Return two passing baseline and candidate profiles with a 6% projection gain."""
    baseline = [
        _profile("0", projection_ms=11000.0, wall_ms=20300.0),
        _profile("0", projection_ms=11200.0, wall_ms=20400.0),
    ]
    candidate = [
        _profile("1", projection_ms=10300.0, wall_ms=20100.0),
        _profile("1", projection_ms=10400.0, wall_ms=20200.0),
    ]
    return baseline, candidate


def _collision_query_profile(
    workers: int,
    *,
    projector_ms: float,
    wall_ms: float,
) -> JsonObject:
    """Build one production profile for the exact mesh-query worker comparison."""
    profile = _profile("1", projection_ms=11000.0, wall_ms=wall_ms)
    profile["runtime_limits"]["thread_environment"]["CLOTH_PBD_COLLISION_QUERY_WORKERS"] = str(
        workers
    )
    profile["python_backend_stage_timings"] = {
        "mesh_collision_projector": {
            "samples": 360,
            "total_ms": projector_ms,
        }
    }
    return profile


def _matched_collision_query_profiles() -> tuple[list[JsonObject], list[JsonObject]]:
    """Return matched worker profiles with a passing projector-stage improvement."""
    baseline = [
        _collision_query_profile(1, projector_ms=2300.0, wall_ms=20400.0),
        _collision_query_profile(1, projector_ms=2250.0, wall_ms=20300.0),
    ]
    candidate = [
        _collision_query_profile(4, projector_ms=1950.0, wall_ms=20300.0),
        _collision_query_profile(4, projector_ms=1900.0, wall_ms=20200.0),
    ]
    return baseline, candidate


def test_collision_query_worker_profiles_pass_both_measured_gates() -> None:
    """Four workers must improve projector time by >=10% without wall regression."""
    baseline, candidate = _matched_collision_query_profiles()

    result = compare_collision_query_worker_profile_sets(baseline, candidate)

    assert result["acceptance"] == "passed"
    assert result["mesh_collision_projector_improvement_percent"] >= 10.0
    assert result["production_wall_time_change_percent"] <= 0.0
    assert result["production_acceptance"] == "passed_all_four_runs"


def test_collision_query_workers_reject_projector_gain_below_ten_percent() -> None:
    """A small exact-query speedup cannot pass the registered 10% stage gate."""
    baseline, candidate = _matched_collision_query_profiles()
    candidate = [
        _collision_query_profile(4, projector_ms=2150.0, wall_ms=20300.0),
        _collision_query_profile(4, projector_ms=2160.0, wall_ms=20200.0),
    ]

    result = compare_collision_query_worker_profile_sets(baseline, candidate)

    assert result["acceptance"] == "rejected"
    assert any("below 10%" in reason for reason in result["rejection_reasons"])


def test_collision_query_workers_reject_wall_regression_and_unmatched_context() -> None:
    """Projector gains cannot hide slower full production or different OpenMP settings."""
    baseline, candidate = _matched_collision_query_profiles()
    candidate = [
        _collision_query_profile(4, projector_ms=1800.0, wall_ms=20600.0),
        _collision_query_profile(4, projector_ms=1850.0, wall_ms=20700.0),
    ]

    result = compare_collision_query_worker_profile_sets(baseline, candidate)

    assert result["acceptance"] == "rejected"
    assert any("wall time regressed" in reason for reason in result["rejection_reasons"])

    baseline, candidate = _matched_collision_query_profiles()
    candidate[0]["runtime_limits"]["thread_environment"]["CLOTH_PBD_OPENMP_TEAM_REUSE"] = "0"
    with pytest.raises(ValueError, match="CLOTH_PBD_OPENMP_TEAM_REUSE must remain 1"):
        compare_collision_query_worker_profile_sets(baseline, candidate)


def test_collision_query_workers_reject_incomplete_projector_timing() -> None:
    """All 360 per-backend-step projector timing samples must be present."""
    baseline, candidate = _matched_collision_query_profiles()
    candidate[0]["python_backend_stage_timings"]["mesh_collision_projector"]["samples"] = 359

    with pytest.raises(
        ValueError, match="mesh collision projector timing sample count is incomplete"
    ):
        compare_collision_query_worker_profile_sets(baseline, candidate)


def test_matched_team_reuse_profiles_pass_both_measured_gates() -> None:
    """A matched candidate with >=5% projection gain and no wall regression passes."""
    baseline, candidate = _matched_profiles()

    result = compare_profile_sets(baseline, candidate)

    assert result["acceptance"] == "passed"
    assert result["projection_improvement_percent"] >= 5.0
    assert result["production_wall_time_change_percent"] <= 0.0
    assert result["production_acceptance"] == "passed_all_four_runs"


def test_team_reuse_rejects_projection_gain_below_five_percent() -> None:
    """A candidate that misses the pre-registered projection gain fails closed."""
    baseline, candidate = _matched_profiles()
    candidate = [
        _profile("1", projection_ms=10800.0, wall_ms=20100.0),
        _profile("1", projection_ms=10900.0, wall_ms=20200.0),
    ]

    result = compare_profile_sets(baseline, candidate)

    assert result["acceptance"] == "rejected"
    assert any("below 5%" in reason for reason in result["rejection_reasons"])


def test_team_reuse_rejects_any_median_production_wall_regression() -> None:
    """A projection improvement cannot hide slower complete production wall time."""
    baseline, candidate = _matched_profiles()
    candidate = [
        _profile("1", projection_ms=10000.0, wall_ms=20500.0),
        _profile("1", projection_ms=10100.0, wall_ms=20600.0),
    ]

    result = compare_profile_sets(baseline, candidate)

    assert result["acceptance"] == "rejected"
    assert any("wall time regressed" in reason for reason in result["rejection_reasons"])


def test_team_reuse_rejects_incomplete_or_failed_physical_acceptance() -> None:
    """Partial audits and any failed physical/visual gate cannot enter the comparison."""
    baseline, candidate = _matched_profiles()
    candidate[0]["scene_steps_completed"] = 89

    with pytest.raises(ValueError, match="scene-step count is incomplete"):
        compare_profile_sets(baseline, candidate)

    baseline, candidate = _matched_profiles()
    candidate[1]["acceptance_gate_results"]["target_clearance_and_penetration"] = False

    with pytest.raises(ValueError, match="seven physical/visual gates"):
        compare_profile_sets(baseline, candidate)


def test_team_reuse_rejects_unmatched_runner_or_solver_context() -> None:
    """Only an identical runner, OpenMP and native build context is comparable."""
    baseline, candidate = _matched_profiles()
    candidate[0]["runtime_limits"]["affinity_cpus"] = [0, 1]

    with pytest.raises(ValueError, match="execution context differs"):
        compare_profile_sets(baseline, candidate)

    baseline, candidate = _matched_profiles()
    candidate[0]["production_settings"]["position_iterations"] = 7

    with pytest.raises(ValueError, match="production solver or collision settings changed"):
        compare_profile_sets(baseline, candidate)


def test_team_reuse_rejects_wrong_native_mode_and_mismatched_grouping() -> None:
    """Each profile must identify its mode and preserve the native conflict-free groups."""
    baseline, candidate = _matched_profiles()
    candidate[0]["runtime_limits"]["thread_environment"]["CLOTH_PBD_OPENMP_TEAM_REUSE"] = "0"

    with pytest.raises(ValueError, match="unexpected CLOTH_PBD_OPENMP_TEAM_REUSE"):
        compare_profile_sets(baseline, candidate)

    baseline, candidate = _matched_profiles()
    candidate[1]["native_constraint_groups"]["group_count"] = 31

    with pytest.raises(ValueError, match="group distribution changed"):
        compare_profile_sets(baseline, candidate)


def test_team_reuse_rejects_incomplete_native_timing_and_wrong_extension() -> None:
    """The comparison must use complete native timer samples from the isolated extension."""
    baseline, candidate = _matched_profiles()
    candidate[0]["native_pypbd_stage_timings"]["position constraints projection"]["samples"] = 359

    with pytest.raises(ValueError, match="timing sample count is incomplete"):
        compare_profile_sets(baseline, candidate)

    baseline, candidate = _matched_profiles()
    candidate[0]["runtime_limits"]["pypbd_module"] = (
        "/opt/conda/envs/freecad/lib/python3.12/site-packages/pypbd.so"
    )

    with pytest.raises(ValueError, match="wrong pyPBD module path"):
        compare_profile_sets(baseline, candidate)


def test_team_reuse_rejects_missing_repetition() -> None:
    """One run in either arm is insufficient evidence for the paired experiment."""
    baseline, candidate = _matched_profiles()

    with pytest.raises(ValueError, match="exactly two baseline"):
        compare_profile_sets(baseline[:1], candidate)


def test_team_reuse_inputs_are_not_mutated() -> None:
    """Validation leaves the four immutable source profile objects unchanged."""
    baseline, candidate = _matched_profiles()
    original = deepcopy((baseline, candidate))

    compare_profile_sets(baseline, candidate)

    assert (baseline, candidate) == original
