# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression contracts for the canonical Python and visual-evidence CI path."""

import ast
import re
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from tests.support.assertions import require
from tools.ci import (
    pytest_collection_contract,
    validate_acceptance,
    validate_manifests,
    validate_realtime_benchmark,
    validate_workbench_benchmark,
)

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SIMULATION_SCREENSHOTS = 1
EXPECTED_SURFACE_PEN_FRAMES = 4
EXPECTED_AVATAR_SHAPE_GIFS = 2


def _require_mapping(value: object, *, label: str) -> dict[str, object]:
    """Return a fixture mapping after checking its runtime shape.

    Args:
        value: Candidate fixture value from a decoded or constructed metrics object.
        label: Human-readable name used when the fixture has an invalid shape.

    Returns:
        The value narrowed to a string-keyed mapping.

    Raises:
        TypeError: If the supplied value is not a dictionary.
    """
    if not isinstance(value, dict):
        msg = f"{label} must be a dictionary"
        raise TypeError(msg)
    return cast("dict[str, object]", value)


def test_collection_plugin_accepts_all_expected_modules() -> None:
    """Verify valid collection metadata is accepted."""
    pytest_collection_contract.validate_collection_contract(
        [
            SimpleNamespace(path=ROOT / "tests" / "test_core.py"),
            SimpleNamespace(path=ROOT / "tests" / "test_mesh.py"),
        ],
        environ={"CLOTH_EXPECTED_TEST_MODULES": "tests/test_core.py\ntests/test_mesh.py"},
    )


def test_collection_plugin_fails_when_a_module_collects_no_items() -> None:
    """Reject a required test module that collects no tests."""
    with pytest.raises(pytest.UsageError, match=re.escape("tests/test_mesh.py")):
        pytest_collection_contract.validate_collection_contract(
            [SimpleNamespace(path=ROOT / "tests" / "test_core.py")],
            environ={"CLOTH_EXPECTED_TEST_MODULES": "tests/test_core.py\ntests/test_mesh.py"},
        )


def test_canonical_python_job_executes_pytest_contract_modules() -> None:
    """Check canonical Python jobs execute the registered collection contract."""
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    start = workflow.index("  python:")
    match = re.search(r"\n  [A-Za-z0-9_-]+:\n", workflow[start + 3 :])
    end = start + 3 + match.start() if match else len(workflow)
    block = workflow[start:end]
    require(
        condition=("group: [core, pattern, sewing, gui, pytest]" in block),
        message="canonical CI contract",
    )
    require(
        condition="python_validation.py" in block,
        message="canonical CI contract",
    )
    runner = (ROOT / "tools" / "ci" / "python_validation.py").read_text(encoding="utf-8")
    require(
        condition=('"tools.ci.pytest_collection_contract"' in runner),
        message="canonical CI contract",
    )
    require(
        condition=("CLOTH_EXPECTED_TEST_MODULES" in runner),
        message="canonical CI contract",
    )
    require(
        condition=("check_test_collection.py" not in runner),
        message="canonical CI contract",
    )
    require(
        condition=("matrix.group != 'gui'" in block),
        message="canonical CI contract",
    )
    require(
        condition=("test-args: gui" in block),
        message="canonical CI contract",
    )


def test_gui_acceptance_validator_uses_visual_artifacts_only() -> None:
    """Require GUI acceptance cases to be verified from visual artifacts."""
    require(
        condition=(
            set(validate_acceptance.CASES)
            == {
                "avatar-pose",
                "avatar-shape-editor",
                "fitting",
                "simulation-quality",
                "surface-pen",
            }
        ),
        message="canonical CI contract",
    )
    require(
        condition=(
            len(validate_acceptance.REQUIRED_SCREENSHOTS["simulation-quality"])
            == EXPECTED_SIMULATION_SCREENSHOTS
        ),
        message="canonical CI contract",
    )
    require(
        condition=(
            len(validate_acceptance.REQUIRED_FRAMES["surface-pen"]) == EXPECTED_SURFACE_PEN_FRAMES
        ),
        message="canonical CI contract",
    )
    require(
        condition=(
            len(validate_acceptance.REQUIRED_GIFS["avatar-shape-editor"])
            == EXPECTED_AVATAR_SHAPE_GIFS
        ),
        message="canonical CI contract",
    )
    require(
        condition=(all(path.suffix == ".png" for path in validate_acceptance.CASES.values())),
        message="canonical CI contract",
    )


def test_simulation_evidence_publisher_uses_authenticated_checked_out_head() -> None:
    """Require PR simulation evidence to publish from the authenticated checked-out head."""
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    start = workflow.index("  publish-pr-simulation-evidence:")
    match = re.search(r"\n  [A-Za-z0-9_-]+:\n", workflow[start + 3 :])
    end = start + 3 + match.start() if match else len(workflow)
    publisher = workflow[start:end]
    require(
        condition=("publish-visual-evidence@" in publisher),
        message="simulation evidence contract",
    )
    require(
        condition=("evidence-head:" in publisher),
        message="simulation evidence contract",
    )
    require(
        condition=("source-sha:" in publisher),
        message="simulation evidence contract",
    )
    require(
        condition=("mode: pr" in publisher),
        message="simulation evidence contract",
    )


def test_main_visual_publisher_uses_local_visual_action_with_pinned_downloads() -> None:
    """Require documentation publication to use the pinned local visual-evidence action."""
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

    require(
        condition=("uses: ./.github/actions/publish-visual-evidence" in publisher),
        message="visual publication contract",
    )
    require(
        condition=("Download Surface Pen artifacts" in action),
        message="visual publication contract",
    )
    require(
        condition=("name: surface-pen" in action),
        message="visual publication contract",
    )
    require(
        condition=("turntable-doc-assets" in action),
        message="visual publication contract",
    )
    require(
        condition=(re.search(r"uses: actions/download-artifact@[0-9a-f]{40}", action) is not None),
        message="visual publication contract",
    )


def test_group_collection_is_checked_during_the_execution_run() -> None:
    """Check the collection plugin validates tests during execution."""
    runner = (ROOT / "tools" / "ci" / "python_validation.py").read_text(encoding="utf-8")
    plugin = ROOT / "tools" / "ci" / "pytest_collection_contract.py"
    old_checker = ROOT / "tools" / "ci" / "check_test_collection.py"

    require(
        condition=(plugin.is_file()),
        message="canonical CI contract",
    )
    require(
        condition=(not old_checker.exists()),
        message="canonical CI contract",
    )
    require(
        condition=('"-p"' in runner),
        message="canonical CI contract",
    )
    require(
        condition=('"tools.ci.pytest_collection_contract"' in runner),
        message="canonical CI contract",
    )
    require(
        condition=("CLOTH_EXPECTED_TEST_MODULES" in runner),
        message="canonical CI contract",
    )
    require(
        condition=("collection_command" not in runner),
        message="canonical CI contract",
    )


def _valid_realtime_benchmark_metrics() -> dict[str, object]:
    """Build a sample that satisfies the sustained 30 FPS metrics contract.

    Returns:
        Complete metrics mapping for a valid tunic realtime benchmark artifact.
    """
    return {
        "schema_version": 1,
        "backend": "position-based-dynamics",
        "fixture": "two-panel-tunic-pattern",
        "particles": 480,
        "panel_count": 2,
        "collision_triangles": 240,
        "frame_budget_ms": validate_realtime_benchmark.FRAME_BUDGET_MS,
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
    """Accept an artifact satisfying the sustained realtime cadence contract."""
    require(
        condition=(
            validate_realtime_benchmark.validate_metrics(_valid_realtime_benchmark_metrics()) == []
        ),
        message="canonical CI contract",
    )


def test_realtime_metric_validator_rejects_tampered_or_slow_samples() -> None:
    """Reject a slow artifact with invalid solver state or profile values."""
    metrics = _valid_realtime_benchmark_metrics()
    metrics["mean_frame_interval_ms"] = 42.0
    metrics["backend_finite"] = False
    profile = _require_mapping(metrics["profile"], label="profile")
    profile["pbd_substeps"] = 8

    errors = validate_realtime_benchmark.validate_metrics(metrics)

    require(
        condition=(any("mean_frame_interval_ms exceeds" in error for error in errors)),
        message="canonical CI contract",
    )
    require(
        condition=("backend_finite must be true" in errors),
        message="canonical CI contract",
    )
    require(
        condition=("profile.pbd_substeps must be 1" in errors),
        message="canonical CI contract",
    )


def test_realtime_metric_validator_rejects_missing_stage_timings() -> None:
    """Reject a realtime artifact missing a required stage timing."""
    metrics = _valid_realtime_benchmark_metrics()
    stages = _require_mapping(metrics["stage_timings"], label="stage timings")
    del stages["viewport_redraw"]

    errors = validate_realtime_benchmark.validate_metrics(metrics)

    require(
        condition=("stage_timings.viewport_redraw must be a JSON object" in errors),
        message="canonical CI contract",
    )


def test_realtime_metric_validator_fails_closed_when_samples_are_missing() -> None:
    """Reject a realtime artifact with too few measured intervals."""
    metrics = _valid_realtime_benchmark_metrics()
    metrics["measured_intervals"] = 9

    errors = validate_realtime_benchmark.validate_metrics(metrics)

    require(
        condition=("measured_intervals must equal frames_requested" in errors),
        message="canonical CI contract",
    )


def test_realtime_benchmark_uses_the_production_timer_and_event_loop() -> None:
    """Require benchmarks to use the production event loop and timer."""
    source_path = ROOT / "tests" / "freecad_realtime_benchmark.py"
    parsed = ast.parse(source_path.read_text(encoding="utf-8"))
    identifiers = {node.id for node in ast.walk(parsed) if isinstance(node, ast.Name)}
    attributes = {node.attr for node in ast.walk(parsed) if isinstance(node, ast.Attribute)}
    string_constants = {
        node.value
        for node in ast.walk(parsed)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    require(
        condition=("_Preview" in identifiers),
        message="canonical CI contract",
    )
    require(
        condition=("_prepare" in identifiers),
        message="canonical CI contract",
    )
    require(
        condition=("QEventLoop" in attributes),
        message="canonical CI contract",
    )
    require(
        condition=("disconnect" in attributes),
        message="canonical CI contract",
    )
    require(
        condition=("connect" in attributes),
        message="canonical CI contract",
    )
    require(
        condition=("WARMUP_FRAMES" in identifiers),
        message="canonical CI contract",
    )
    require(
        condition=("FRAMES" in identifiers),
        message="canonical CI contract",
    )
    require(
        condition=("stage_timings" in identifiers),
        message="canonical CI contract",
    )
    require(
        condition=("solver_step" in string_constants),
        message="canonical CI contract",
    )
    require(
        condition=("viewport_redraw" in string_constants),
        message="canonical CI contract",
    )
    require(
        condition=(
            "validate_realtime_benchmark.py"
            in (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
                encoding="utf-8"
            )
        ),
        message="canonical CI contract",
    )


def test_tunic_manifest_gate_accepts_current_realtime_metrics_schema() -> None:
    """Accept a tunic manifest using the current realtime metrics schema."""
    vars(validate_manifests)["_validate_realtime_metrics"](_valid_realtime_benchmark_metrics())


def test_tunic_manifest_gate_rejects_new_schema_above_the_30_fps_budget() -> None:
    """Reject current-schema tunic metrics exceeding the unchanged 30 FPS budget."""
    metrics = _valid_realtime_benchmark_metrics()
    metrics["p95_frame_interval_ms"] = validate_realtime_benchmark.FRAME_BUDGET_MS + 0.1

    with pytest.raises(SystemExit, match="realtime performance gate failed"):
        vars(validate_manifests)["_validate_realtime_metrics"](metrics)


def test_tunic_manifest_gate_preserves_the_legacy_metrics_contract() -> None:
    """Retain the legacy metrics gate for older artifacts."""
    legacy_metrics = {
        "finite": True,
        "mean_frame_ms": 16.0,
        "frame_budget_ms": 33.3333333333,
        "p95_frame_ms": 45.0,
    }
    vars(validate_manifests)["_validate_realtime_metrics"](legacy_metrics)

    legacy_metrics["p95_frame_ms"] = 50.1
    with pytest.raises(SystemExit, match="realtime performance gate failed"):
        vars(validate_manifests)["_validate_realtime_metrics"](legacy_metrics)


def _valid_workbench_benchmark_metrics(workbench: str = "Pattern") -> dict[str, object]:
    """Build an artifact matching the production workbench benchmark schema.

    Args:
        workbench: Workbench name written into the benchmark artifact.

    Returns:
        Complete sample mapping matching the version-two benchmark contract.
    """
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
    require(
        condition=(
            validate_workbench_benchmark.validate_metrics(
                _valid_workbench_benchmark_metrics(), "Pattern"
            )
            == []
        ),
        message="canonical CI contract",
    )


def test_workbench_benchmark_validator_rejects_wrong_schema_and_sample_count() -> None:
    """Schema drift and incomplete repeated initialization remain blocking."""
    metrics = _valid_workbench_benchmark_metrics()
    metrics["schema"] = 1
    workbenches = _require_mapping(metrics["workbenches"], label="workbenches")
    pattern = _require_mapping(workbenches["Pattern"], label="pattern metrics")
    pattern["initialize_samples"] = 6

    errors = validate_workbench_benchmark.validate_metrics(metrics, "Pattern")

    require(
        condition=("schema must be 2" in errors),
        message="canonical CI contract",
    )
    require(
        condition=("initialize_samples must equal repeats" in errors),
        message="canonical CI contract",
    )


def test_workbench_benchmark_validator_rejects_wrong_matrix_entry_and_nonfinite_timing() -> None:
    """A stale artifact for another matrix job or malformed timing cannot pass."""
    metrics = _valid_workbench_benchmark_metrics()
    require(
        condition=(
            "workbenches must contain only 'Sewing'"
            in validate_workbench_benchmark.validate_metrics(metrics, "Sewing")
        ),
        message="workbench matrix contract",
    )

    workbenches = _require_mapping(metrics["workbenches"], label="workbenches")
    pattern = _require_mapping(workbenches["Pattern"], label="pattern metrics")
    pattern["initialize_ms"] = float("nan")

    require(
        condition=(
            "initialize_ms must be a finite non-negative number"
            in validate_workbench_benchmark.validate_metrics(metrics, "Pattern")
        ),
        message="workbench matrix contract",
    )


def test_workbench_benchmark_matrix_uses_the_dedicated_schema_validator() -> None:
    """Workbench startup output must not be routed through the realtime PBD validator."""
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    benchmark_job = workflow.split("  benchmark:", maxsplit=1)[1]

    require(
        condition=(
            "tools/ci/validate_workbench_benchmark.py artifacts/benchmark.json" in benchmark_job
        ),
        message="canonical CI contract",
    )
    require(
        condition=("validate_realtime_benchmark.py artifacts/benchmark.json" not in benchmark_job),
        message="canonical CI contract",
    )
    require(
        condition=(
            "python3 tools/ci/validate_realtime_benchmark.py "
            "artifacts/freecad-realtime/metrics.json" in workflow
        ),
        message="canonical CI contract",
    )


def test_static_preflight_runs_public_api_regressions() -> None:
    """Run diagnostic and avatar adapter API regressions before broad static gates."""
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    command_start = workflow.find("tests/test_avatar_fitting_coordinate_contract.py")
    command_end = workflow.find("pyright -p pyrightconfig.json", command_start)
    command = workflow[command_start:command_end] if command_end > command_start else ""
    required_tests = (
        "tests/test_avatar_runtime_api_adapter.py",
        "tests/test_cloth_diagnostics.py",
        "tests/test_avatar_fitting_anchor_refresh.py",
    )

    require(
        condition=(
            command_start >= 0
            and command_end > command_start
            and all(path in command for path in required_tests)
        ),
        message="static preflight must run the diagnostic and avatar API regressions",
    )
