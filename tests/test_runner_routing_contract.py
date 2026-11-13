# Copyright (C) 2026 FreeCAD Cloth contributors
"""Contract checks for the canonical local runner topology and trust boundaries."""

import os
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.ci.pytest_collection_contract import (
    missing_requested_modules,
    validate_collection_contract,
)

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "canonical-execution.yml"


def _job_block(source: str, job: str) -> str:
    """Extract one named job block from workflow source text.

    Args:
        source: Full workflow YAML text.
        job: Job identifier whose indented block should be extracted.

    Returns:
        The requested block, including its lines, but excluding the next job.
    """
    marker = f"  {job}:\n"
    start = source.index(marker)
    remainder = source[start + len(marker) :]
    lines = remainder.splitlines(keepends=True)
    block: list[str] = []
    for line in lines:
        if line.startswith("  ") and not line.startswith("    ") and line.rstrip().endswith(":"):
            break
        block.append(line)
    return "".join(block)


def test_one_canonical_workflow() -> None:
    """Require the canonical reusable workflow and its three callers only."""
    workflow_dir = ROOT / ".github" / "workflows"
    workflows = sorted(path.name for path in workflow_dir.glob("*.yml"))
    assert workflows == [
        "canonical-execution.yml",
        "commit-validation.yml",
        "main-publication.yml",
        "merge-validation.yml",
    ]
    shared = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_call:" in shared
    assert "workflow_run:" not in shared


def test_pull_requests_are_trusted_before_using_the_local_runner() -> None:
    """Allow same-repository, non-Dependabot PRs onto the persistent runner only."""
    workflow_dir = ROOT / ".github" / "workflows"
    entry = (workflow_dir / "commit-validation.yml").read_text(encoding="utf-8")
    fast = _job_block(entry, "fast-feedback")
    full = _job_block(entry, "explicit-full-validation")
    assert "pull_request:" in entry
    assert "pull_request_target:" not in entry
    for block in (fast, full):
        assert "github.event.pull_request.head.repo.full_name == github.repository" in block
        assert "github.event.pull_request.user.login != 'dependabot[bot]'" in block
    assert "execution_mode: fast" in fast
    assert "execution_mode: full" in full
    assert "[full-validation]" in entry


def test_every_canonical_job_uses_only_the_self_hosted_docker_runner() -> None:
    """Require every canonical job to avoid GitHub-hosted runner minutes."""
    source = WORKFLOW.read_text(encoding="utf-8")
    job_source = source.split("\njobs:\n", 1)[1]
    blocks = re.findall(
        r"(?ms)^  ([A-Za-z0-9_-]+):\n(.*?)(?=^  [A-Za-z0-9_-]+:\n|\Z)",
        job_source,
    )
    assert blocks
    for name, block in blocks:
        assert "runs-on: [self-hosted, linux, x64, docker]" in block, (
            f"{name} must use the configured self-hosted Docker runner."
        )
    assert "ubuntu-latest" not in source
    assert "runner_watchdog" not in source
    assert "fallback_source_run" not in source


def test_local_readiness_gates_quality_and_image_work() -> None:
    """Start static checks and the PBD image build only after local readiness."""
    source = WORKFLOW.read_text(encoding="utf-8")
    quality = _job_block(source, "agent-quality")
    image = _job_block(source, "pbd_validation_image")
    readiness = _job_block(source, "local_runner_readiness")
    assert "needs: [local_runner_readiness]" in quality
    assert "needs: [local_runner_readiness]" in image
    assert "docker info" in readiness
    assert "github.event_name == 'merge_group'" in readiness
    assert "commits/${HEAD_SHA}/pulls" in readiness


def test_manual_validation_and_publication_have_no_hosted_fallback() -> None:
    """Keep dispatch, schedule, merge-queue, and publication paths local-only."""
    workflows = ROOT / ".github" / "workflows"
    commit = (workflows / "commit-validation.yml").read_text(encoding="utf-8")
    merge = (workflows / "merge-validation.yml").read_text(encoding="utf-8")
    publication = (workflows / "main-publication.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in commit
    assert "runner_mode" not in commit
    assert "fallback_source_run" not in commit
    assert "execution_mode: full" in commit
    assert "runs-on: [self-hosted, linux, x64, docker]" in merge
    assert "runner_mode" not in merge
    assert "fallback_source_run" not in merge
    assert "push:" in publication
    assert "branches: [main]" in publication
    assert "workflow_dispatch:" not in publication
    assert "ubuntu-latest" not in merge + publication


def test_reusable_dependency_environments_and_docker_images_are_persistent() -> None:
    """Reuse the FreeCAD image, dependency-keyed venv, pip cache, and local Docker images."""
    quality = _job_block(WORKFLOW.read_text(encoding="utf-8"), "agent-quality")
    wrapper = (ROOT / "tools" / "ci" / "run_strict_quality.sh").read_text(encoding="utf-8")
    runner = (ROOT / "tools" / "ci" / "strict_quality.py").read_text(encoding="utf-8")
    image_action = (ROOT / ".github" / "actions" / "pbd-image" / "action.yml").read_text(
        encoding="utf-8"
    )
    assert "needs: [local_runner_readiness, pbd_validation_image]" in quality
    assert "needs.pbd_validation_image.outputs.image" in quality
    assert "bash tools/ci/run_strict_quality.sh" in quality
    assert "RUNNER_TOOL_CACHE" in wrapper
    assert "PIP_CACHE_DIR" in wrapper
    assert "PRE_COMMIT_HOME" in wrapper
    assert "docker image inspect" in wrapper
    assert "docker run" in wrapper
    assert "--system-site-packages" in runner
    assert "torch==2.8.0+cpu" in runner
    assert "ready_marker_is_current" in runner
    assert "docker image inspect" in image_action
    assert "docker pull" in image_action


def test_no_privileged_runner_discovery_or_second_workflow() -> None:
    """Forbid privileged runner discovery and duplicate workflow entry points."""
    workflow_dir = ROOT / ".github" / "workflows"
    sources = {path.name: path.read_text(encoding="utf-8") for path in workflow_dir.glob("*.yml")}
    assert set(sources) == {
        "canonical-execution.yml",
        "commit-validation.yml",
        "main-publication.yml",
        "merge-validation.yml",
    }
    assert all("workflow_run:" not in source for source in sources.values())
    shared = sources["canonical-execution.yml"]
    for marker in ("CLOTH_RUNNER_DISCOVERY_TOKEN", "runner_router:", "*/5 * * * *"):
        assert marker not in shared
    maintenance = _job_block(shared, "maintenance-cleanup")
    assert "runs-on: [self-hosted, linux, x64, docker]" in maintenance
    assert "github.event_name == 'schedule'" in maintenance
    assert "RUN MAINTENANCE CLEANUP" in maintenance


def test_pr_checkout_is_credential_free_and_uses_head_sha() -> None:
    """Keep PR checkout pinned to its head SHA without persisted checkout credentials."""
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "github.event.pull_request.head.sha" in source
    assert "persist-credentials: false" in source


def test_collection_contract_passes_when_every_requested_module_collects() -> None:
    """Accept the collection contract when each requested module is present."""
    result = missing_requested_modules(
        ("tests/test_one.py", "tests/test_two.py"),
        ("tests/test_one.py", "tests/test_two.py", "tests/test_two.py"),
    )
    assert result == ()


def test_collection_contract_rejects_a_requested_module_with_zero_items() -> None:
    """Reject a requested module when it collects no pytest items."""
    expected = (ROOT / "tests" / "test_one.py", ROOT / "tests" / "test_empty.py")
    collected = SimpleNamespace(path=expected[0])
    with pytest.raises(pytest.UsageError, match=r"tests/test_empty\.py"):
        validate_collection_contract(
            [collected],
            environ={"CLOTH_EXPECTED_TEST_MODULES": os.pathsep.join(map(str, expected))},
        )

def test_freecad_container_transfers_checkout_and_returns_evidence() -> None:
    """Transfer checked-out source and generated evidence without host bind mounts."""
    action_path = ROOT / ".github" / "actions" / "freecad-container" / "action.yml"
    action = action_path.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert (
        'git -C "$workspace" archive --format=tar --output="$workspace_archive" HEAD'
        in action
    )
    assert (
        'docker cp "$workspace_archive" "$container_id:/tmp/freecad-workspace.tar"'
        in action
    )
    assert 'docker cp "$container_id:/workspace/$relative_path/." "$stage_directory/"' in action
    assert 'copy_back_directory "artifacts" "$output_root/artifacts"' in action
    assert 'copy_back_directory "docs/images/generated" "$output_root/generated"' in action
    assert '-v "$GITHUB_WORKSPACE:/workspace:rw"' not in action
    assert "uses: ./.github/actions/freecad-container" in workflow
    assert "Uhrendoktor/freecad-cloth/.github/actions/freecad-container@" not in workflow
    assert "--shm-size=1g" in action


