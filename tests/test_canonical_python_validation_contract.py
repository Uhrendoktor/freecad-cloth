# Copyright (C) 2026 FreeCAD Cloth contributors
import ast
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_collection_plugin_accepts_all_expected_modules():
    from tools.ci.pytest_collection_contract import validate_collection_contract

    validate_collection_contract(
        [
            SimpleNamespace(path=ROOT / "tests" / "test_core.py"),
            SimpleNamespace(path=ROOT / "tests" / "test_mesh.py"),
        ],
        environ={"CLOTH_EXPECTED_TEST_MODULES": "tests/test_core.py\ntests/test_mesh.py"},
    )


def test_collection_plugin_fails_when_a_module_collects_no_items():
    from tools.ci.pytest_collection_contract import validate_collection_contract

    with pytest.raises(pytest.UsageError, match="tests/test_mesh.py"):
        validate_collection_contract(
            [SimpleNamespace(path=ROOT / "tests" / "test_core.py")],
            environ={"CLOTH_EXPECTED_TEST_MODULES": "tests/test_core.py\ntests/test_mesh.py"},
        )


def test_canonical_python_job_executes_pytest_contract_modules():
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    start = workflow.index("  python:")
    match = re.search(r"\n  [A-Za-z0-9_-]+:\n", workflow[start + 3 :])
    end = start + 3 + match.start() if match else len(workflow)
    block = workflow[start:end]
    assert "group: [core, pattern, sewing, gui, pytest]" in block
    assert "python_validation.py" in block
    runner = (ROOT / "tools" / "ci" / "python_validation.py").read_text(encoding="utf-8")
    assert '"tools.ci.pytest_collection_contract"' in runner
    assert "CLOTH_EXPECTED_TEST_MODULES" in runner
    assert "check_test_collection.py" not in runner
    assert "matrix.group != 'gui'" in block
    assert "test-args: gui" in block


def test_gui_acceptance_validator_uses_visual_artifacts_only():
    from tools.ci import validate_acceptance

    assert set(validate_acceptance.CASES) == {
        "avatar-pose",
        "avatar-shape-editor",
        "fitting",
        "surface-pen",
    }
    assert len(validate_acceptance.REQUIRED_FRAMES["surface-pen"]) == 4
    assert len(validate_acceptance.REQUIRED_GIFS["avatar-shape-editor"]) == 2
    assert all(path.suffix == ".png" for path in validate_acceptance.CASES.values())


def test_simulation_evidence_publisher_uses_authenticated_checked_out_head():
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    start = workflow.index("  publish-pr-simulation-evidence:")
    match = re.search(r"\n  [A-Za-z0-9_-]+:\n", workflow[start + 3 :])
    end = start + 3 + match.start() if match else len(workflow)
    publisher = workflow[start:end]
    assert "publish-visual-evidence@" in publisher
    assert "evidence-head:" in publisher
    assert "source-sha:" in publisher
    assert "mode: pr" in publisher


def test_main_visual_publisher_uses_local_visual_action_with_pinned_downloads() -> None:
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    start = workflow.index("  publish-readme-turntables:")
    match = re.search(r"\n  [A-Za-z0-9_-]+:\n", workflow[start + 3 :])
    end = start + 3 + match.start() if match else len(workflow)
    publisher = workflow[start:end]
    action = (ROOT / ".github" / "actions" / "publish-visual-evidence" / "action.yml").read_text(
        encoding="utf-8"
    )

    assert "uses: ./.github/actions/publish-visual-evidence" in publisher
    assert "Download Surface Pen artifacts" in action
    assert "name: surface-pen" in action
    assert "turntable-doc-assets" in action
    assert re.search(r"uses: actions/download-artifact@[0-9a-f]{40}", action)


def test_group_collection_is_checked_during_the_execution_run():
    runner = (ROOT / "tools" / "ci" / "python_validation.py").read_text(encoding="utf-8")
    plugin = ROOT / "tools" / "ci" / "pytest_collection_contract.py"
    old_checker = ROOT / "tools" / "ci" / "check_test_collection.py"

    assert plugin.is_file()
    assert not old_checker.exists()
    assert '"-p"' in runner
    assert '"tools.ci.pytest_collection_contract"' in runner
    assert "CLOTH_EXPECTED_TEST_MODULES" in runner
    assert "collection_command" not in runner


def _valid_realtime_benchmark_metrics() -> dict[str, object]:
    from tools.ci.validate_realtime_benchmark import FRAME_BUDGET_MS

    return {
        "schema_version": 1,
        "backend": "position-based-dynamics",
        "fixture": "two-panel-tunic-pattern",
        "particles": 480,
        "panel_count": 2,
        "collision_triangles": 240,
        "frame_budget_ms": FRAME_BUDGET_MS,
        "frames_requested": 120,
        "warmup_frames_requested": 30,
        "measured_intervals": 120,
        "observed_ticks": 150,
        "expected_ticks": 150,
        "frames_advanced": 150,
        "timed_out": False,
        "backend_finite": True,
        "published_state_finite": True,
        "mean_frame_interval_ms": 16.4,
        "p95_frame_interval_ms": 18.2,
        "mean_callback_ms": 5.1,
        "p95_callback_ms": 6.3,
        "stage_timings": {
            "advance_preview_frame": {
                "samples": 120,
                "mean_ms": 8.0,
                "p95_ms": 9.0,
                "max_ms": 10.0,
            },
            "solver_step": {"samples": 120, "mean_ms": 2.0, "p95_ms": 2.5, "max_ms": 3.0},
            "state_publish": {"samples": 120, "mean_ms": 6.0, "p95_ms": 7.0, "max_ms": 8.0},
            "mesh_write": {"samples": 240, "mean_ms": 4.0, "p95_ms": 5.0, "max_ms": 6.0},
            "overlay_schedule": {"samples": 60, "mean_ms": 0.1, "p95_ms": 0.2, "max_ms": 0.3},
            "viewport_redraw": {"samples": 120, "mean_ms": 3.0, "p95_ms": 4.0, "max_ms": 5.0},
        },
        "profile": {
            "quality_preset": "Fast",
            "particle_distance_mm": 40.0,
            "solver_iterations": 1,
            "solver_substeps": 1,
            "pbd_substeps": 1,
        },
        "runtime": {
            "platform": "Linux-test",
            "python_version": "3.12.0",
            "freecad_version": "1.0.0",
            "cpu_count": 4,
            "libgl_always_software": "1",
        },
    }


def test_realtime_metric_validator_accepts_a_valid_sustained_30_fps_sample() -> None:
    from tools.ci.validate_realtime_benchmark import validate_metrics

    assert validate_metrics(_valid_realtime_benchmark_metrics()) == []


def test_realtime_metric_validator_rejects_tampered_or_slow_samples() -> None:
    from tools.ci.validate_realtime_benchmark import validate_metrics

    metrics = _valid_realtime_benchmark_metrics()
    metrics["mean_frame_interval_ms"] = 42.0
    metrics["backend_finite"] = False
    profile = metrics["profile"]
    assert isinstance(profile, dict)
    profile["pbd_substeps"] = 8

    errors = validate_metrics(metrics)

    assert any("mean_frame_interval_ms exceeds" in error for error in errors)
    assert "backend_finite must be true" in errors
    assert "profile.pbd_substeps must be 1" in errors


def test_realtime_metric_validator_rejects_missing_stage_timings() -> None:
    from tools.ci.validate_realtime_benchmark import validate_metrics

    metrics = _valid_realtime_benchmark_metrics()
    stages = metrics["stage_timings"]
    assert isinstance(stages, dict)
    del stages["viewport_redraw"]

    errors = validate_metrics(metrics)

    assert "stage_timings.viewport_redraw must be a JSON object" in errors


def test_realtime_metric_validator_fails_closed_when_samples_are_missing() -> None:
    from tools.ci.validate_realtime_benchmark import validate_metrics

    metrics = _valid_realtime_benchmark_metrics()
    metrics["measured_intervals"] = 9

    errors = validate_metrics(metrics)

    assert "measured_intervals must equal frames_requested" in errors


def test_realtime_benchmark_uses_the_production_timer_and_event_loop() -> None:
    source_path = ROOT / "tests" / "freecad_realtime_benchmark.py"
    parsed = ast.parse(source_path.read_text(encoding="utf-8"))
    identifiers = {node.id for node in ast.walk(parsed) if isinstance(node, ast.Name)}
    attributes = {node.attr for node in ast.walk(parsed) if isinstance(node, ast.Attribute)}
    string_constants = {
        node.value
        for node in ast.walk(parsed)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert "_Preview" in identifiers
    assert "_prepare" in identifiers
    assert "QEventLoop" in attributes
    assert "disconnect" in attributes
    assert "connect" in attributes
    assert "WARMUP_FRAMES" in identifiers
    assert "FRAMES" in identifiers
    assert "stage_timings" in identifiers
    assert "solver_step" in string_constants
    assert "viewport_redraw" in string_constants
    assert "validate_realtime_benchmark.py" in (
        ROOT / ".github" / "workflows" / "canonical-execution.yml"
    ).read_text(encoding="utf-8")


def test_tunic_manifest_gate_accepts_current_realtime_metrics_schema() -> None:
    from tools.ci.validate_manifests import _validate_realtime_metrics

    _validate_realtime_metrics(_valid_realtime_benchmark_metrics())


def test_tunic_manifest_gate_rejects_new_schema_above_the_30_fps_budget() -> None:
    from tools.ci.validate_manifests import _validate_realtime_metrics
    from tools.ci.validate_realtime_benchmark import FRAME_BUDGET_MS

    metrics = _valid_realtime_benchmark_metrics()
    metrics["p95_frame_interval_ms"] = FRAME_BUDGET_MS + 0.1

    with pytest.raises(SystemExit, match="realtime performance gate failed"):
        _validate_realtime_metrics(metrics)


def test_tunic_manifest_gate_preserves_the_legacy_metrics_contract() -> None:
    from tools.ci.validate_manifests import _validate_realtime_metrics

    legacy_metrics = {
        "finite": True,
        "mean_frame_ms": 16.0,
        "frame_budget_ms": 33.3333333333,
        "p95_frame_ms": 45.0,
    }
    _validate_realtime_metrics(legacy_metrics)

    legacy_metrics["p95_frame_ms"] = 50.1
    with pytest.raises(SystemExit, match="realtime performance gate failed"):
        _validate_realtime_metrics(legacy_metrics)


def _valid_workbench_benchmark_metrics(workbench: str = "Pattern") -> dict[str, object]:
    """Build an artifact matching the production workbench benchmark schema."""
    return {
        "schema": 2,
        "python": "3.12.14",
        "freecad_version": ["1", "1", "0", "build"],
        "repeats": 7,
        "workbenches": {
            workbench: {
                "class_lookup_ms": 0.0,
                "construct_ms": 0.039,
                "initialize_ms": 0.253,
                "initialize_samples": 7,
                "registered_commands": 18,
                "python_files": 24,
                "nonblank_loc": 6065,
                "related_test_files": 1,
                "related_tests": ["test_pattern.py"],
                "cloth_command_tokens": 93,
            }
        },
    }


def test_workbench_benchmark_validator_accepts_matching_schema_two_artifact() -> None:
    """Fresh workbench output satisfies its own strict, distinct schema contract."""
    from tools.ci.validate_workbench_benchmark import validate_metrics

    assert validate_metrics(_valid_workbench_benchmark_metrics(), "Pattern") == []


def test_workbench_benchmark_validator_rejects_wrong_schema_and_sample_count() -> None:
    """Schema drift and incomplete repeated initialization remain blocking."""
    from tools.ci.validate_workbench_benchmark import validate_metrics

    metrics = _valid_workbench_benchmark_metrics()
    metrics["schema"] = 1
    workbenches = metrics["workbenches"]
    assert isinstance(workbenches, dict)
    pattern = workbenches["Pattern"]
    assert isinstance(pattern, dict)
    pattern["initialize_samples"] = 6

    errors = validate_metrics(metrics, "Pattern")

    assert "schema must be 2" in errors
    assert "initialize_samples must equal repeats" in errors


def test_workbench_benchmark_validator_rejects_wrong_matrix_entry_and_nonfinite_timing() -> None:
    """A stale artifact for another matrix job or malformed timing cannot pass."""
    from tools.ci.validate_workbench_benchmark import validate_metrics

    metrics = _valid_workbench_benchmark_metrics()
    assert "workbenches must contain only 'Sewing'" in validate_metrics(metrics, "Sewing")

    workbenches = metrics["workbenches"]
    assert isinstance(workbenches, dict)
    pattern = workbenches["Pattern"]
    assert isinstance(pattern, dict)
    pattern["initialize_ms"] = float("nan")

    assert "initialize_ms must be a finite non-negative number" in validate_metrics(
        metrics, "Pattern"
    )


def test_workbench_benchmark_matrix_uses_the_dedicated_schema_validator() -> None:
    """Workbench startup output must not be routed through the realtime PBD validator."""
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    benchmark_job = workflow.split("  benchmark:", maxsplit=1)[1]

    assert "tools/ci/validate_workbench_benchmark.py artifacts/benchmark.json" in benchmark_job
    assert "validate_realtime_benchmark.py artifacts/benchmark.json" not in benchmark_job
    assert (
        "python3 tools/ci/validate_realtime_benchmark.py artifacts/freecad-realtime/metrics.json"
        in workflow
    )
