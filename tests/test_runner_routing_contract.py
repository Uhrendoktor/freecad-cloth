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


def test_pull_requests_are_trusted_before_using_the_configured_hosted_runner() -> None:
    """Allow same-repository, non-Dependabot PRs into the configured hosted group."""
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


def test_every_canonical_job_uses_the_configured_github_hosted_runner() -> None:
    """Route canonical jobs through a configured GPU group or CPU-only fallback."""
    source = WORKFLOW.read_text(encoding="utf-8")
    job_source = source.split("\njobs:\n", 1)[1]
    blocks = re.findall(
        r"(?ms)^  ([A-Za-z0-9_-]+):\n(.*?)(?=^  [A-Za-z0-9_-]+:\n|\Z)",
        job_source,
    )
    assert blocks
    for name, block in blocks:
        expected = (
            "runs-on: ubuntu-latest"
            if name == "guarded-rebase-pr"
            else "runs-on: ${{ fromJSON(inputs.runner_target) }}"
        )
        assert expected in block, f"{name} must use its configured GitHub-hosted runner."
        assert "self-hosted" not in block
    assert "runner_target:" in source
    assert "default: ubuntu-latest" in source
    assert "runner_watchdog" not in source
    assert "fallback_source_run" not in source


def test_cuda_runner_is_optional_and_freecad_container_keeps_cpu_fallback() -> None:
    """Pass NVIDIA devices only when both the host and container probes succeed."""
    action = (ROOT / ".github" / "actions" / "freecad-container" / "action.yml").read_text(
        encoding="utf-8"
    )
    assert "command -v nvidia-smi" in action
    assert "nvidia-smi -L" in action
    assert "docker run --rm --gpus all" in action
    assert "gpu_docker_args=(--gpus all)" in action
    assert 'cuda_mode="cpu-fallback"' in action
    assert "freecad-container-compute=$cuda_mode" in action

    profile = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    preview = (ROOT / "tests" / "freecad_realtime_benchmark.py").read_text(encoding="utf-8")
    for field in (
        '"cuda_runner_probe"',
        '"cuda_runner_mode"',
        '"cuda_runner_reason"',
        '"cuda_device_nodes"',
        '"simulation_backend_device": "cpu"',
    ):
        assert field in profile
    assert '"simulation_backend_device": "cpu"' in preview


def test_hosted_runner_readiness_checks_docker_workspace_transfer() -> None:
    """Require checkout and the bidirectional workspace probe before work starts."""
    source = WORKFLOW.read_text(encoding="utf-8")
    readiness = _job_block(source, "local_runner_readiness")
    assert "actions/checkout@" in readiness
    assert "persist-credentials: false" in readiness
    assert "python3 tools/ci/check_docker_workspace_transfer.py" in readiness


def test_runner_readiness_gates_quality_and_image_work() -> None:
    """Start static checks and the PBD image build only after hosted readiness."""
    source = WORKFLOW.read_text(encoding="utf-8")
    quality = _job_block(source, "agent-quality")
    image = _job_block(source, "pbd_validation_image")
    readiness = _job_block(source, "local_runner_readiness")
    assert "needs: [local_runner_readiness, pbd_validation_image]" in quality
    assert "needs: [local_runner_readiness]" in image
    assert "python3 tools/ci/check_docker_workspace_transfer.py" in readiness
    assert "github.event_name == 'merge_group'" in readiness
    assert "commits/${HEAD_SHA}/pulls" in readiness


def test_manual_validation_and_publication_use_gpu_group_with_cpu_fallback() -> None:
    """Route dispatch, publication and merge validation through the hosted runner setting."""
    workflows = ROOT / ".github" / "workflows"
    commit = (workflows / "commit-validation.yml").read_text(encoding="utf-8")
    merge = (workflows / "merge-validation.yml").read_text(encoding="utf-8")
    publication = (workflows / "main-publication.yml").read_text(encoding="utf-8")
    for source in (commit, merge, publication):
        assert "FREECAD_CUDA_RUNNER_GROUP != ''" in source
        assert 'format(\'{{"group":"{0}"}}\'' in source
        assert "runner_mode" not in source
        assert "fallback_source_run" not in source
    assert "workflow_dispatch:" in commit
    assert "execution_mode: full" in commit
    assert "runs-on: ubuntu-latest" in merge
    assert "push:" in publication
    assert "branches: [main]" in publication
    assert "workflow_dispatch:" not in publication


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
    assert "docker create" in wrapper
    assert "docker cp" in wrapper
    assert "docker start --attach" in wrapper
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
    assert "runs-on: ${{ fromJSON(inputs.runner_target) }}" in maintenance
    assert "github.event_name == 'schedule'" in maintenance
    assert "RUN MAINTENANCE CLEANUP" in maintenance


def test_pr_checkout_is_credential_free_and_uses_head_sha() -> None:
    """Keep PR checkout pinned to its head SHA without persisted checkout credentials."""
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "github.event.pull_request.head.sha" in source
    assert "persist-credentials: false" in source


def test_jobs_check_out_before_loading_local_composite_actions() -> None:
    """Require an explicit checkout before GitHub resolves repository-local actions."""
    source = WORKFLOW.read_text(encoding="utf-8")
    job_source = source.split("\njobs:\n", 1)[1]
    blocks = re.findall(
        r"(?ms)^  ([A-Za-z0-9_-]+):\n(.*?)(?=^  [A-Za-z0-9_-]+:\n|\Z)",
        job_source,
    )
    assert blocks
    for name, block in blocks:
        local_action = block.find("uses: ./.github/actions/")
        if local_action < 0:
            continue
        checkout = block.find("uses: actions/checkout@")
        assert checkout >= 0
        assert checkout < local_action, (
            f"{name} must check out the revision before loading a local action."
        )
        first_action = block[local_action:].splitlines()[0]
        if first_action == "uses: ./.github/actions/freecad-test":
            step_end = block.find("\n      - ", local_action)
            if step_end < 0:
                step_end = len(block)
            first_action_step = block[local_action:step_end]
            assert 'checkout: "false"' in first_action_step, (
                f"{name} should reuse the job checkout instead of checking out twice."
            )


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

    assert 'git -C "$workspace" archive --format=tar --output="$workspace_archive" HEAD' in action
    assert "for relative_path in artifacts docs/images/generated; do" in action
    assert 'tar -rf "$workspace_archive" -C "$workspace" "$relative_path"' in action
    assert 'docker cp "$workspace_archive" "$container_id:/tmp/freecad-workspace.tar"' in action
    assert 'docker cp "$container_id:/workspace/$relative_path/." "$stage_directory/"' in action
    assert 'copy_back_directory "artifacts" "$output_root/artifacts"' in action
    assert 'copy_back_directory "docs/images/generated" "$output_root/generated"' in action
    assert '-v "$GITHUB_WORKSPACE:/workspace:rw"' not in action
    assert "uses: ./.github/actions/freecad-container" in workflow
    assert "Uhrendoktor/freecad-cloth/.github/actions/freecad-container@" not in workflow
    assert "Uhrendoktor/freecad-cloth/.github/actions/freecad-test@" not in workflow
    assert "--shm-size=1g" in action
