# Copyright (C) 2026 FreeCAD Cloth contributors
"""Validate the repository CI structure and hard runtime contracts."""

from __future__ import annotations

import fnmatch
import json
import os
import re
import sys
from pathlib import Path

if __package__:
    from tools.ci.command_runner import CommandOptions, run_command
else:
    from command_runner import CommandOptions, run_command

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = ROOT / ".github/workflows"
WORKFLOW = WORKFLOW_DIR / "canonical-execution.yml"
COMMIT_VALIDATION_WORKFLOW = WORKFLOW_DIR / "commit-validation.yml"
MERGE_VALIDATION_WORKFLOW = WORKFLOW_DIR / "merge-validation.yml"
MAIN_PUBLICATION_WORKFLOW = WORKFLOW_DIR / "main-publication.yml"
WORKFLOW_FILES = tuple(
    sorted(
        (
            WORKFLOW,
            COMMIT_VALIDATION_WORKFLOW,
            MERGE_VALIDATION_WORKFLOW,
            MAIN_PUBLICATION_WORKFLOW,
        )
    )
)
PYRIGHT_CONFIG = ROOT / "pyrightconfig.json"
PYRIGHT_LEGACY_CONFIG = ROOT / "pyrightconfig.agent-strict.json"
MAX_REUSABLE_WORKFLOW_LINES = 750
MAX_CI_TIMEOUT_SECONDS = 180
REQUIRED = (
    ROOT / ".github/actions/freecad-test/action.yml",
    ROOT / ".github/actions/freecad-container/action.yml",
    ROOT / ".github/actions/pbd-image/action.yml",
    ROOT / ".github/actions/publish-visual-evidence/action.yml",
    ROOT / "tools/ci/run_freecad.py",
    ROOT / "tools/ci/command_runner.py",
    ROOT / "tools/ci/command_runner.py",
    ROOT / "tools/ci/python_validation.py",
    ROOT / "tools/ci/validate_acceptance.py",
    ROOT / "tools/ci/validate_manifests.py",
    ROOT / "tools/ci/visual_evidence.py",
    ROOT / "tools/ci/publish_visual_evidence.py",
    ROOT / "tools/ci/capture_pypbd_provenance.py",
    ROOT / "tools/ci/check_artifact_budget.py",
    ROOT / "tools/ci/create_agent_observation_bundle.py",
    ROOT / "tools/ci/check_no_source_rewriting.py",
    ROOT / "tools/check_documentation_contract.py",
    ROOT / "tools/ci/validate_workbench_benchmark.py",
)

# The whole repository is checked in global strict mode. No file is grandfathered.
PYRIGHT_EXPECTED_INCLUDE = (".",)
PYRIGHT_EXPECTED_EXCLUDE: tuple[str, ...] = ()

QUALITY_RUNNER_COMMANDS = ('bash tools/ci/run_strict_quality.sh "$QUALITY_IMAGE"',)

PYTHON_POLICY_COMMANDS = (
    "python tools/ci/check_no_source_rewriting.py",
    "python tools/check_documentation_contract.py",
)
RUFF_COMMANDS = (
    'xargs -0 -r python -m ruff format --check < "$RUNNER_TEMP/python-files.zlist"',
    'xargs -0 -r python -m ruff check < "$RUNNER_TEMP/python-files.zlist"',
)


def missing_typecheck_commands(workflow_text: str) -> tuple[str, ...]:
    """Return the blocking quality-runner command when it is not standalone.

    The canonical workflow delegates its pinned-runtime command inventory to the
    strict runner. The runner's tested inventory contains the standalone Pyright
    invocation, so this boundary must itself be a standalone shell command.

    Args:
        workflow_text: Full canonical workflow text to inspect.

    Returns:
        Blocking strict-quality runner commands absent as standalone lines.
    """
    command_lines = {line.strip() for line in workflow_text.splitlines()}
    return tuple(
        command for command in QUALITY_RUNNER_COMMANDS if command not in command_lines
    )


def missing_python_policy_commands(workflow_text: str) -> tuple[str, ...]:
    """Return required repository Python policy gates missing from the canonical workflow.

    Args:
        workflow_text: Full canonical workflow text to inspect.

    Returns:
        Python policy commands that are missing from the workflow.
    """
    command_lines: set[str] = set()
    for line in workflow_text.splitlines():
        command = line.strip()
        if command.startswith("run: "):
            command = command.removeprefix("run: ").strip()
        command_lines.add(command)
    return tuple(command for command in PYTHON_POLICY_COMMANDS if command not in command_lines)


def missing_ruff_commands(workflow_text: str) -> tuple[str, ...]:
    """Return required standalone Ruff commands missing from the canonical workflow.

    Args:
        workflow_text: Full canonical workflow text to inspect.

    Returns:
        Ruff commands that are absent as standalone shell lines.
    """
    command_lines: set[str] = set()
    for line in workflow_text.splitlines():
        command = line.strip()
        if command.startswith("run: "):
            command = command.removeprefix("run: ").strip()
        command_lines.add(command)
    return tuple(command for command in RUFF_COMMANDS if command not in command_lines)


def _pyright_path_is_included(path: str, include: list[str]) -> bool:
    """Return whether a source path is covered by one include entry.

    Args:
        path: Repository-relative source path being checked.
        include: Pyright include entries that define the checked scope.

    Returns:
        Whether an include entry covers the supplied source path.
    """
    normalized = Path(path).as_posix()
    for entry in include:
        target = Path(entry).as_posix()
        if target in {".", "**"}:
            return True
        if normalized == target:
            return True
        if not target.endswith(".py") and normalized.startswith(target.rstrip("/") + "/"):
            return True
    return False


def _pyright_path_is_excluded(path: str, exclude: list[str]) -> bool:
    """Return whether a source path is covered by a declared exclusion pattern.

    Args:
        path: Repository-relative source path being checked.
        exclude: Pyright exclusion patterns to compare against the path.

    Returns:
        Whether any exclusion pattern matches the source path.
    """
    return any(fnmatch.fnmatchcase(Path(path).as_posix(), pattern) for pattern in exclude)


def added_production_python_modules(base: str) -> tuple[str, ...]:
    """Find new production Python modules added relative to a pull request base.

    Args:
        base: Target branch used as the comparison base.

    Returns:
        Newly added production Python module paths.
    """
    result = run_command(
        [
            "git",
            "diff",
            "--name-only",
            "--diff-filter=A",
            "--no-renames",
            f"origin/{base}...HEAD",
            "--",
            "freecad_cloth",
        ],
        options=CommandOptions(capture_output=True, timeout=30),
    )
    return tuple(
        sorted(
            Path(path).as_posix()
            for path in (result.stdout or "").splitlines()
            if path.endswith(".py")
        )
    )


def pyright_coverage_contract_violations(
    config_text: str,
    added_modules: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """Require Pyright strict mode to cover the repository without exclusions.

    Args:
        config_text: Contents of the Pyright configuration file.
        added_modules: Newly added Python modules to verify against repository-wide scope.

    Returns:
        Pyright coverage-contract violations found in the configuration.
    """
    try:
        config = json.loads(config_text)
    except json.JSONDecodeError:
        return ("<invalid pyrightconfig.json>",)

    violations: list[str] = []
    if config.get("include") != list(PYRIGHT_EXPECTED_INCLUDE):
        violations.append("<Pyright must include the entire repository root>")
    if config.get("exclude", []) != list(PYRIGHT_EXPECTED_EXCLUDE):
        violations.append("<Pyright exclude scope must not hide repository files>")
    if config.get("typeCheckingMode") != "strict":
        violations.append("<Pyright must use global strict type checking>")
    if config.get("strict", []) != []:
        violations.append("<Pyright strict path list must not substitute for global strict mode>")
    if config.get("reportMissingImports", "error") != "error":
        violations.append("<Pyright missing-import diagnostics must remain errors>")
    if config.get("reportMissingModuleSource", "error") != "error":
        violations.append("<Pyright missing-module-source diagnostics must remain errors>")
    if config.get("reportMissingTypeStubs", "error") != "error":
        violations.append("<Pyright missing-type-stub diagnostics must remain errors>")
    if config.get("reportImportCycles", "error") != "error":
        violations.append("<Pyright import-cycle diagnostics must remain errors>")

    uncovered_modules = tuple(
        path
        for path in added_modules
        if not _pyright_path_is_included(path, list(PYRIGHT_EXPECTED_INCLUDE))
        or _pyright_path_is_excluded(path, list(PYRIGHT_EXPECTED_EXCLUDE))
    )
    violations.extend(
        f"<new Python module is outside Pyright repository-wide coverage: {path}>"
        for path in uncovered_modules
    )
    return tuple(violations)


def _validate_workflow_dispatch_contract(text: str) -> None:
    """Validate the shared workflow's size and trigger boundaries.

    Args:
        text: Full canonical reusable workflow source.

    Raises:
        SystemExit: If workflow structure or event ownership is invalid.
    """
    lines = text.splitlines()
    if len(lines) > MAX_REUSABLE_WORKFLOW_LINES:
        msg = f"reusable workflow is {len(lines)} lines; limit is {MAX_REUSABLE_WORKFLOW_LINES}"
        raise SystemExit(msg)
    trigger_block = text.split("\nenv:", 1)[0]
    if "workflow_call:" not in trigger_block or re.search(
        r"(?m)^  (push|pull_request|merge_group|workflow_dispatch|schedule):", trigger_block
    ):
        msg = (
            "canonical-execution.yml must be callable only; "
            "event triggers belong in entry workflows"
        )
        raise SystemExit(msg)


def _validate_entrypoint_workflows() -> None:
    """Require fast feedback, explicit full validation, merge gating, and publication ownership.

    Raises:
        SystemExit: If event-specific workflows do not preserve the required validation gates.
    """
    commit_workflow = COMMIT_VALIDATION_WORKFLOW.read_text(encoding="utf-8")
    merge_workflow = MERGE_VALIDATION_WORKFLOW.read_text(encoding="utf-8")
    publication_workflow = MAIN_PUBLICATION_WORKFLOW.read_text(encoding="utf-8")
    full_validation_workflow = merge_workflow.split("  full-validation:", 1)[1].split(
        "  required-pre-merge-validation:", 1
    )[0]
    merge_gate = merge_workflow.split("  required-pre-merge-validation:", 1)[1]

    required_commit_markers = (
        "pull_request:",
        "execution_mode: fast",
        "explicit-full-validation:",
        "[full-validation]",
        "types: [opened, synchronize, reopened, ready_for_review, edited]",
        "workflow_dispatch:",
    )
    invalid_commit_workflow = (
        any(marker not in commit_workflow for marker in required_commit_markers)
        or "merge_group:" in commit_workflow
    )
    required_merge_markers = (
        "merge_group:",
        "name: Required pre-merge validation",
    )
    invalid_merge_workflow = (
        any(marker not in merge_workflow for marker in required_merge_markers)
        or "workflow_dispatch:" in merge_workflow
        or "pull_request:" in merge_workflow
        or "if: ${{ always() }}" not in merge_gate
        or "needs: [full-validation]" not in merge_gate
    )
    invalid_full_validation = "execution_mode: full" not in full_validation_workflow
    if invalid_commit_workflow or invalid_merge_workflow or invalid_full_validation:
        msg = (
            "commit-validation.yml must provide fast feedback; "
            "merge-validation.yml must gate merge-group full validation"
        )
        raise SystemExit(msg)

    required_publication_markers = (
        "push:",
        "branches: [main]",
        "execution_mode: publication",
    )
    if any(marker not in publication_workflow for marker in required_publication_markers):
        msg = "main-publication.yml must be main-only and call canonical publication mode"
        raise SystemExit(msg)


def _validate_reusable_workflow_trust(text: str) -> None:
    """Reject duplicate concurrency ownership, unsafe triggers, and unvalidated publication.

    Args:
        text: Full canonical reusable workflow source.

    Raises:
        SystemExit: If the reusable workflow bypasses its validation or trust boundaries.
    """
    required_markers = (
        "Required validation gate",
        "No successful full-validation run matched source tree",
        '--event "${event}" --status success',
        "Explicit full validation / Required validation gate",
    )
    merge_workflow = MERGE_VALIDATION_WORKFLOW.read_text(encoding="utf-8")
    if any(marker not in text for marker in required_markers) or (
        "Required pre-merge validation" not in merge_workflow
    ):
        msg = (
            "reusable workflow must enforce mode-specific validation "
            "and refuse unvalidated publication"
        )
        raise SystemExit(msg)
    if "\nconcurrency:\n" in text.split("\njobs:\n", 1)[0]:
        msg = "concurrency belongs to entry workflows, not the shared reusable workflow"
        raise SystemExit(msg)
    if "pull_request_target" in text:
        msg = "pull_request_target is forbidden"
        raise SystemExit(msg)


def _validate_python_quality_contracts(text: str) -> None:
    """Require blocking type, repository-policy, Ruff, and staged coverage gates.

    Args:
        text: Full canonical reusable workflow source.

    Raises:
        SystemExit: If a required quality gate or reviewed type-check scope is missing.
    """
    missing_typecheck = missing_typecheck_commands(text)
    if missing_typecheck:
        raise SystemExit(
            "canonical workflow is missing its standalone blocking strict-quality runner: "
            + ", ".join(missing_typecheck)
        )
    missing_python_policies = missing_python_policy_commands(text)
    if missing_python_policies:
        raise SystemExit(
            "canonical workflow is missing standalone Python policy commands: "
            + ", ".join(missing_python_policies)
        )
    if PYRIGHT_LEGACY_CONFIG.exists():
        msg = "duplicate Pyright config must be removed; maintain only pyrightconfig.json"
        raise SystemExit(msg)
    try:
        pyright_config = json.loads(PYRIGHT_CONFIG.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        msg = "pyrightconfig.json must be valid JSON"
        raise SystemExit(msg) from error
    if pyright_config.get("typeCheckingMode") != "strict":
        msg = "pyrightconfig.json must apply strict type checking repository-wide"
        raise SystemExit(msg)
    if pyright_config.get("strict", []):
        msg = "pyrightconfig.json must not replace global strict mode with a path allowlist"
        raise SystemExit(msg)
    missing_ruff = missing_ruff_commands(text)
    if missing_ruff:
        raise SystemExit(
            "canonical workflow must run Ruff over every tracked Python file: "
            + ", ".join(missing_ruff)
        )
    base_ref = os.environ.get("BASE_REF") or os.environ.get("GITHUB_BASE_REF")
    added_modules = added_production_python_modules(base_ref) if base_ref else ()
    coverage_violations = pyright_coverage_contract_violations(
        PYRIGHT_CONFIG.read_text(encoding="utf-8"), added_modules
    )
    if coverage_violations:
        raise SystemExit(
            "Pyright production-module coverage policy is invalid: "
            + ", ".join(coverage_violations)
        )


def _validate_command_safety(text: str) -> None:
    """Require reusable workflow calls to respect container and checkout boundaries.

    Args:
        text: Full canonical reusable workflow source.

    Raises:
        SystemExit: If workflow code manages Docker directly or skips the FreeCAD test action.
    """
    if re.search(r"\bdocker\s+(run|create|cp)\b", text):
        msg = "Docker lifecycle belongs in .github/actions/freecad-container"
        raise SystemExit(msg)
    allowed_action_references = (
        "uses: ./.github/actions/freecad-test",
        "uses: $/.github/actions/freecad-test",
        "uses: Uhrendoktor/freecad-cloth/.github/actions/freecad-test@",
    )
    if not any(reference in text for reference in allowed_action_references):
        msg = "canonical workflow must use freecad-test"
        raise SystemExit(msg)


def _validate_required_components() -> None:
    """Validate required CI files and immutable PBD/container/timeout policies.

    Raises:
        SystemExit: If a required action, policy marker, or CI helper is missing.
    """
    for path in REQUIRED:
        if not path.is_file():
            msg = f"missing required CI component: {path}"
            raise SystemExit(msg)
    pbd_action = (ROOT / ".github/actions/pbd-image/action.yml").read_text(encoding="utf-8")
    forbidden_pbd_markers = ("upload-artifact", "docker save", "pbd-validation-image")
    if any(marker in pbd_action for marker in forbidden_pbd_markers):
        msg = "PBD validation image must never be serialized as a workflow artifact"
        raise SystemExit(msg)
    container_action = (ROOT / ".github/actions/freecad-container/action.yml").read_text(
        encoding="utf-8"
    )
    if "download-artifact" in container_action or "pbd-validation-image" in container_action:
        msg = "FreeCAD container action must use GHCR only; workflow image artifacts are forbidden"
        raise SystemExit(msg)
    if "180s" not in container_action or "timeout-seconds" not in container_action:
        msg = "FreeCAD container action must retain its 180-second pull contract"
        raise SystemExit(msg)
    freecad_action = (ROOT / ".github/actions/freecad-test/action.yml").read_text(encoding="utf-8")
    if (
        'default: "120"' not in freecad_action
        or "timeout-seconds: ${{ inputs.timeout-seconds }}" not in freecad_action
    ):
        msg = "freecad-test must pass its default-120 timeout to the container action"
        raise SystemExit(msg)
    if "FREECAD_APPLICATION_TIMEOUT_SECONDS=" not in freecad_action:
        msg = "freecad-test must scope non-default budgets to the FreeCAD process"
        raise SystemExit(msg)


def _validate_action_pinning() -> None:
    """Require external actions to use full commit SHAs and keep command timeouts bounded.

    Raises:
        SystemExit: If an action reference is mutable or a CI timeout exceeds the approved bound.
    """
    ci_files = [*WORKFLOW_FILES, *sorted((ROOT / ".github/actions").rglob("action.yml"))]
    for ci_file in ci_files:
        ci_text = ci_file.read_text(encoding="utf-8")
        for match in re.finditer(r"uses:\s+([^\s#]+)", ci_text):
            value = match.group(1)
            if value.startswith(("./", "$/", "Uhrendoktor/freecad-cloth/")):
                continue
            if "@" not in value or not re.fullmatch(
                r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}", value
            ):
                msg = f"CI action is not pinned to a full SHA: {ci_file}: {value}"
                raise SystemExit(msg)

        for match in re.finditer(r"timeout[^\n]*?\b(\d+)s\b", ci_text):
            if int(match.group(1)) > MAX_CI_TIMEOUT_SECONDS:
                msg = (
                    f"CI timeout exceeds {MAX_CI_TIMEOUT_SECONDS} seconds: "
                    f"{ci_file}: {match.group(0).strip()}"
                )
                raise SystemExit(msg)


def main() -> int:
    """Validate the repository CI structure and hard runtime contracts.

    Returns:
        Process status indicating whether the CI structure is valid.

    Raises:
        SystemExit: If a required workflow or type-check gate is missing.
    """
    files = tuple(sorted(WORKFLOW_DIR.glob("*.y*ml")))
    if files != WORKFLOW_FILES:
        msg = (
            "expected commit/merge/publication entry points plus one reusable workflow, "
            f"found: {files}"
        )
        raise SystemExit(msg)
    text = WORKFLOW.read_text(encoding="utf-8")
    _validate_workflow_dispatch_contract(text)
    _validate_entrypoint_workflows()
    _validate_reusable_workflow_trust(text)
    _validate_python_quality_contracts(text)
    _validate_command_safety(text)
    _validate_required_components()
    _validate_action_pinning()
    sys.stdout.write(f"ci-structure=passed workflow_lines={len(text.splitlines())}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
