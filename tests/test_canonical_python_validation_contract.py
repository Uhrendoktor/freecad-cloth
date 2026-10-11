import ast
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_collection_plugin_accepts_all_expected_modules(monkeypatch):
    from tools.ci.pytest_collection_contract import pytest_collection_modifyitems

    monkeypatch.setenv(
        "CLOTH_EXPECTED_TEST_MODULES",
        "tests/test_core.py\ntests/test_mesh.py",
    )
    pytest_collection_modifyitems(
        [
            SimpleNamespace(path=ROOT / "tests" / "test_core.py"),
            SimpleNamespace(path=ROOT / "tests" / "test_mesh.py"),
        ]
    )


def test_collection_plugin_fails_when_a_module_collects_no_items(monkeypatch):
    from tools.ci.pytest_collection_contract import pytest_collection_modifyitems

    monkeypatch.setenv(
        "CLOTH_EXPECTED_TEST_MODULES",
        "tests/test_core.py\ntests/test_mesh.py",
    )
    with pytest.raises(pytest.UsageError, match="tests/test_mesh.py"):
        pytest_collection_modifyitems([SimpleNamespace(path=ROOT / "tests" / "test_core.py")])


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


def test_main_visual_publisher_pins_surface_pen_artifact_download_revision() -> None:
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    start = workflow.index("  publish-readme-turntables:")
    match = re.search(r"\n  [A-Za-z0-9_-]+:\n", workflow[start + 3 :])
    end = start + 3 + match.start() if match else len(workflow)
    publisher = workflow[start:end]
    # This immutable revision adds the required Surface Pen artifact download.
    assert "@f63948fe20421061904324bcef128a4fcfc69965" in publisher


# Exact-head validation recut marker; behavior unchanged.
# Final exact-head cube diagnostic trigger marker; behavior unchanged.


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
    assert "_Preview" in identifiers
    assert "_prepare" in identifiers
    assert "QEventLoop" in attributes
    assert "disconnect" in attributes
    assert "connect" in attributes
    assert "WARMUP_FRAMES" in identifiers
    assert "FRAMES" in identifiers
    assert "validate_realtime_benchmark.py" in (
        ROOT / ".github" / "workflows" / "canonical-execution.yml"
    ).read_text(encoding="utf-8")
