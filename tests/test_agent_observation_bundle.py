"""Behavioral tests for the compact agent-observation manifest writer."""

import hashlib
import json
from pathlib import Path

import pytest

from tools.ci.create_agent_observation_bundle import (
    MAX_EVIDENCE_BYTES,
    ObservationBundleError,
    create_observation_bundle,
)


def _fixture(tmp_path: Path) -> tuple[dict[str, str], Path]:
    """Create a minimal set of files and GitHub metadata for a test run."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    root = tmp_path / "artifacts"
    root.mkdir()
    (root / "metrics.json").write_text('{"vertex_count": 8}', encoding="utf-8")
    (root / "view.png").write_bytes(b"\x89PNG\r\n\x1a\nsmall-test-image")
    event_path = tmp_path / "event.json"
    event_path.write_text('{"pull_request": {"number": 2651}}', encoding="utf-8")
    environment = {
        "GITHUB_REPOSITORY": "Uhrendoktor/freecad-cloth",
        "GITHUB_SHA": "deadbeef",
        "CLOTH_HEAD_SHA": "headsha",
        "GITHUB_WORKFLOW": "Canonical execution",
        "GITHUB_JOB": "diagnostic-pbd-contact",
        "GITHUB_EVENT_NAME": "pull_request",
        "GITHUB_RUN_ID": "12345",
        "GITHUB_RUN_ATTEMPT": "2",
        "GITHUB_EVENT_PATH": str(event_path),
        "RUNNER_OS": "Linux",
        "RUNNER_ARCH": "X64",
        "OBSERVATION_TEST_SCRIPT": "tests/freecad_pbd_contact_diagnostics.py",
        "OBSERVATION_IMAGE": "ghcr.io/example/freecad@sha256:abc",
        "CLOTH_SIMULATION_BACKEND": "position-based-dynamics",
    }
    return environment, root


def _create(tmp_path: Path, specifications: list[str]) -> dict[str, object]:
    """Create a manifest for the test fixture."""
    environment, _root = _fixture(tmp_path)
    return create_observation_bundle(
        workspace=tmp_path,
        observation_root="artifacts",
        output_value="artifacts/agent-observation.json",
        specifications=specifications,
        label="focused diagnostic",
        environment=environment,
    )


def test_manifest_records_provenance_evidence_hashes_and_relative_paths(tmp_path: Path):
    manifest = _create(tmp_path, ["metrics=metrics.json", "visual=view.png"])

    assert manifest["schema"] == "freecad-cloth.agent-observation"
    assert manifest["schema_version"] == 1
    context = manifest["context"]
    assert isinstance(context, dict)
    assert context["commit_sha"] == "headsha"
    assert context["pull_request_number"] == 2651
    evidence = manifest["evidence"]
    assert isinstance(evidence, list)
    assert [item["path"] for item in evidence] == ["metrics.json", "view.png"]
    assert evidence[0]["sha256"] == hashlib.sha256(b'{"vertex_count": 8}').hexdigest()
    assert evidence[1]["media_type"] == "image/png"
    written = json.loads(
        (tmp_path / "artifacts" / "agent-observation.json").read_text(encoding="utf-8")
    )
    assert written == manifest
    execution = manifest["execution"]
    assert isinstance(execution, dict)
    assert execution["test_script"] == "tests/freecad_pbd_contact_diagnostics.py"


def test_manifest_can_be_created_without_github_metadata(tmp_path: Path):
    root = tmp_path / "artifacts"
    root.mkdir(parents=True)
    (root / "summary.json").write_text("{}", encoding="utf-8")

    manifest = create_observation_bundle(
        workspace=tmp_path,
        observation_root="artifacts",
        output_value="artifacts/agent-observation.json",
        specifications=["summary=summary.json"],
        label="",
        environment={},
    )

    context = manifest["context"]
    assert isinstance(context, dict)
    assert context["repository"] is None
    assert context["run_url"] is None
    assert manifest["label"] is None


def test_missing_evidence_fails_closed(tmp_path: Path):
    with pytest.raises(ObservationBundleError, match="required evidence is missing"):
        _create(tmp_path / "missing", ["metrics=missing.json"])


def test_traversal_and_symlinks_are_rejected(tmp_path: Path):
    with pytest.raises(ObservationBundleError, match="unsafe evidence path"):
        _create(tmp_path / "traversal", ["metrics=../metrics.json"])

    environment, root = _fixture(tmp_path / "symlink")
    try:
        (root / "outside.json").symlink_to(root / "metrics.json")
    except OSError:
        pytest.skip("symlinks unavailable in this environment")
    with pytest.raises(ObservationBundleError, match="symbolic links"):
        create_observation_bundle(
            workspace=tmp_path / "symlink",
            observation_root="artifacts",
            output_value="artifacts/agent-observation.json",
            specifications=["metrics=outside.json"],
            label="",
            environment=environment,
        )


def test_logs_are_not_valid_evidence(tmp_path: Path):
    environment, root = _fixture(tmp_path)
    (root / "run.log").write_text("verbose output", encoding="utf-8")
    with pytest.raises(ObservationBundleError, match="unsupported evidence extension"):
        create_observation_bundle(
            workspace=tmp_path,
            observation_root="artifacts",
            output_value="artifacts/agent-observation.json",
            specifications=["metrics=run.log"],
            label="",
            environment=environment,
        )


def test_individual_file_budget_is_enforced(tmp_path: Path):
    environment, root = _fixture(tmp_path)
    (root / "large.json").write_bytes(b"x" * 4_000_001)
    with pytest.raises(ObservationBundleError, match="exceeds 4000000 bytes"):
        create_observation_bundle(
            workspace=tmp_path,
            observation_root="artifacts",
            output_value="artifacts/agent-observation.json",
            specifications=["summary=large.json"],
            label="",
            environment=environment,
        )


def test_aggregate_evidence_budget_is_enforced(tmp_path: Path):
    environment, root = _fixture(tmp_path)
    (root / "one.json").write_bytes(b"x" * 2_600_000)
    (root / "two.json").write_bytes(b"y" * 2_600_000)
    with pytest.raises(ObservationBundleError, match="selected evidence totals"):
        create_observation_bundle(
            workspace=tmp_path,
            observation_root="artifacts",
            output_value="artifacts/agent-observation.json",
            specifications=["summary=one.json", "summary=two.json"],
            label="",
            environment=environment,
        )
    assert MAX_EVIDENCE_BYTES == 5_000_000


def test_duplicate_paths_and_manifest_location_are_rejected(tmp_path: Path):
    with pytest.raises(ObservationBundleError, match="duplicate evidence path"):
        _create(tmp_path / "duplicate", ["metrics=metrics.json", "summary=metrics.json"])

    environment, _root = _fixture(tmp_path / "output-location")
    with pytest.raises(ObservationBundleError, match="directly inside observation-root"):
        create_observation_bundle(
            workspace=tmp_path / "output-location",
            observation_root="artifacts",
            output_value="agent-observation.json",
            specifications=["metrics=metrics.json"],
            label="",
            environment=environment,
        )
