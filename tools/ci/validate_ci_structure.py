"""Validate the repository CI structure and hard runtime contracts."""

from __future__ import annotations

import fnmatch
import json
import os
import re
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = ROOT / ".github/workflows"
WORKFLOW = WORKFLOW_DIR / "canonical-execution.yml"
COMMIT_VALIDATION_WORKFLOW = WORKFLOW_DIR / "commit-validation.yml"
MAIN_PUBLICATION_WORKFLOW = WORKFLOW_DIR / "main-publication.yml"
WORKFLOW_FILES = tuple(sorted((WORKFLOW, COMMIT_VALIDATION_WORKFLOW, MAIN_PUBLICATION_WORKFLOW)))
PYRIGHT_CONFIG = ROOT / "pyrightconfig.json"
PYRIGHT_LEGACY_CONFIG = ROOT / "pyrightconfig.agent-strict.json"
TY_CONFIG = ROOT / "ty.toml"
REQUIRED = (
    ROOT / ".github/actions/freecad-test/action.yml",
    ROOT / ".github/actions/freecad-container/action.yml",
    ROOT / ".github/actions/pbd-image/action.yml",
    ROOT / ".github/actions/publish-visual-evidence/action.yml",
    ROOT / "tools/ci/run_freecad.py",
    ROOT / "tools/ci/python_validation.py",
    ROOT / "tools/ci/validate_acceptance.py",
    ROOT / "tools/ci/validate_manifests.py",
    ROOT / "tools/ci/visual_evidence.py",
    ROOT / "tools/ci/publish_visual_evidence.py",
    ROOT / "tools/ci/capture_pypbd_provenance.py",
    ROOT / "tools/ci/check_artifact_budget.py",
    ROOT / "tools/ci/create_agent_observation_bundle.py",
    ROOT / "tools/ci/timeout_contract.py",
    ROOT / "tools/ci/check_pydantic_models.py",
    ROOT / "tools/ci/check_no_source_rewriting.py",
    ROOT / "tools/ci/validate_workbench_benchmark.py",
)

# Stage semantic type checking deliberately: these paths form the reviewed
# blocking Pyright inventory. Add modules here only after their diagnostics
# have been triaged. Changed-file annotation ratcheting still covers every
# Python file, including GUI/command surfaces outside this inventory.
PYRIGHT_EXPECTED_INCLUDE = (
    "freecad_cloth/common",
    "freecad_cloth/shared",
    "freecad_cloth/pattern/PatternGeometry.py",
    "freecad_cloth/pattern/PatternIR.py",
    "freecad_cloth/pattern/PatternModel.py",
    "freecad_cloth/pattern/PatternPdfExport.py",
    "freecad_cloth/pattern/PatternSvgValidation.py",
    "freecad_cloth/sewing/SeamGraph.py",
    "freecad_cloth/sewing/SewingCorrespondence.py",
    "freecad_cloth/simulation/DrapeFailureClassifier.py",
    "freecad_cloth/simulation/ClothBackend.py",
    "freecad_cloth/simulation/ClothSolver.py",
    "freecad_cloth/simulation/DrapeTarget.py",
    "freecad_cloth/simulation/SimulationQuality.py",
    "freecad_cloth/simulation/SimulationObjects.py",
    "freecad_cloth/simulation/SimulationQualityRuntime.py",
    "freecad_cloth/simulation/PositionBasedDynamicsBackend.py",
    "freecad_cloth/simulation/MeshCollisionProjector.py",
    "freecad_cloth/avatar/MakeHumanTargets.py",
    "freecad_cloth/avatar/AnnyAvatarBackend.py",
)
PYRIGHT_EXPECTED_EXCLUDE = (
    "**/*Gui.py",
    "**/*Commands.py",
    "**/workbench.py",
)
PYRIGHT_EXPECTED_STRICT = (
    "freecad_cloth/simulation/DrapeFailureClassifier.py",
    "freecad_cloth/simulation/ClothBackend.py",
    "freecad_cloth/simulation/ClothSolver.py",
)

TYPECHECK_COMMANDS = (
    "python tools/ci/check_explicit_any_annotations.py",
    "pyright -p pyrightconfig.json",
    "ty check --output-format github freecad_cloth/simulation/DrapeFailureClassifier.py freecad_cloth/simulation/ClothBackend.py freecad_cloth/simulation/ClothSolver.py",
    "python tools/ci/check_changed_python_types.py",
)

PYTHON_POLICY_COMMANDS = (
    "python tools/ci/check_pydantic_models.py",
    "python tools/ci/check_no_source_rewriting.py",
    "python -m pytest -q tests/test_no_source_rewriting.py",
)
SOURCE_REWRITING_POLICY_COMMANDS = ("python tools/ci/check_no_source_rewriting.py",)

RUFF_COMMANDS = (
    'xargs -0 -r python -m ruff format --check < "$RUNNER_TEMP/python-files.zlist"',
    'xargs -0 -r python -m ruff check < "$RUNNER_TEMP/python-files.zlist"',
)


def missing_typecheck_commands(workflow_text: str) -> tuple[str, ...]:
    """Return required blocking type gates not present as standalone shell commands.

    Exact-line matching is intentional: a failing command inside an AND chain
    can be exempt from Bash errexit handling, allowing CI to continue.
    """
    command_lines = {line.strip() for line in workflow_text.splitlines()}
    return tuple(command for command in TYPECHECK_COMMANDS if command not in command_lines)


def missing_python_policy_commands(workflow_text: str) -> tuple[str, ...]:
    """Return required repository Python policy gates missing from the canonical workflow."""
    command_lines = {line.strip() for line in workflow_text.splitlines()}
    return tuple(command for command in PYTHON_POLICY_COMMANDS if command not in command_lines)


def missing_source_rewriting_policy_commands(workflow_text: str) -> tuple[str, ...]:
    """Require the blocking source-rewriting prohibition in the canonical workflow."""
    command_lines = {line.strip() for line in workflow_text.splitlines()}
    return tuple(
        command for command in SOURCE_REWRITING_POLICY_COMMANDS if command not in command_lines
    )


def source_rewriting_policy_tests_are_blocking(workflow_text: str) -> bool:
    """Require policy regression tests in the blocking pytest step."""
    return any(
        "python -m pytest" in line and "tests/test_no_source_rewriting.py" in line
        for line in workflow_text.splitlines()
    )


def _pyright_path_is_included(path: str, include: list[str]) -> bool:
    """Return whether a source path is covered by one include entry."""
    normalized = Path(path).as_posix()
    for entry in include:
        target = Path(entry).as_posix()
        if normalized == target:
            return True
        if not target.endswith(".py") and normalized.startswith(target.rstrip("/") + "/"):
            return True
    return False


def _pyright_path_is_excluded(path: str, exclude: list[str]) -> bool:
    """Return whether a source path is covered by a declared exclusion pattern."""
    return any(fnmatch.fnmatchcase(Path(path).as_posix(), pattern) for pattern in exclude)


def added_production_python_modules(base: str) -> tuple[str, ...]:
    """Find new production Python modules added relative to a pull request base."""
    result = subprocess.run(
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
        check=True,
        capture_output=True,
        text=True,
    )
    return tuple(
        sorted(Path(path).as_posix() for path in result.stdout.splitlines() if path.endswith(".py"))
    )


def pyright_coverage_contract_violations(
    config_text: str,
    added_modules: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """Require the reviewed staged Pyright include/exclude inventory to remain intact.

    The current production tree has a large pre-existing type-error backlog.
    Semantic coverage is widened incrementally; changing the scope requires an
    explicit inventory update alongside diagnostic triage. Every changed Python
    file is independently subject to the annotation-debt non-regression gate.
    """
    try:
        config = json.loads(config_text)
    except json.JSONDecodeError:
        return ("<invalid pyrightconfig.json>",)

    include = config.get("include")
    exclude = config.get("exclude", [])
    if include != list(PYRIGHT_EXPECTED_INCLUDE):
        return ("<Pyright include scope differs from the reviewed inventory>",)
    if exclude != list(PYRIGHT_EXPECTED_EXCLUDE):
        return ("<Pyright exclude scope differs from the reviewed inventory>",)

    missing_paths = tuple(path for path in PYRIGHT_EXPECTED_INCLUDE if not (ROOT / path).exists())
    if missing_paths:
        return tuple(f"<Pyright inventory path does not exist: {path}>" for path in missing_paths)

    uncovered_modules = tuple(
        path
        for path in added_modules
        if not _pyright_path_is_included(path, include)
        and not _pyright_path_is_excluded(path, exclude)
    )
    return tuple(
        f"<new Python module is outside Pyright include/exclude scope: {path}>"
        for path in uncovered_modules
    )


def ty_warnings_are_blocking(config_text: str) -> bool:
    """Return whether ty is configured to fail when it emits warnings."""
    try:
        config = tomllib.loads(config_text)
    except tomllib.TOMLDecodeError:
        return False
    terminal = config.get("terminal")
    return isinstance(terminal, dict) and terminal.get("error-on-warning") is True


def main() -> int:
    """Validate the repository CI structure and hard runtime contracts."""
    files = tuple(sorted(WORKFLOW_DIR.glob("*.y*ml")))
    if files != WORKFLOW_FILES:
        raise SystemExit(f"expected thin commit/main entry points plus one reusable workflow, found: {files}")
    text = WORKFLOW.read_text(encoding="utf-8")
    lines = text.splitlines()
    if len(lines) > 750:
        raise SystemExit(f"reusable workflow is {len(lines)} lines; limit is 750")
    trigger_block = text.split("\nenv:", 1)[0]
    if "workflow_call:" not in trigger_block or re.search(
        r"(?m)^  (push|pull_request|merge_group|workflow_dispatch|schedule):", trigger_block
    ):
        raise SystemExit(
            "canonical-execution.yml must be callable only; event triggers belong in entry workflows"
        )
    commit_workflow = COMMIT_VALIDATION_WORKFLOW.read_text(encoding="utf-8")
    publication_workflow = MAIN_PUBLICATION_WORKFLOW.read_text(encoding="utf-8")
    if (
        "pull_request:" not in commit_workflow
        or "merge_group:" not in commit_workflow
        or "execution_mode: fast" not in commit_workflow
        or "execution_mode: full" not in commit_workflow
        or "github.event.pull_request.draft == false" not in commit_workflow
        or "name: Required pre-merge validation" not in commit_workflow
    ):
        raise SystemExit(
            "commit-validation.yml must run fast feedback, full validation, and a required pre-merge gate"
        )
    if (
        "push:" not in publication_workflow
        or "branches: [main]" not in publication_workflow
        or "execution_mode: publication" not in publication_workflow
    ):
        raise SystemExit(
            "main-publication.yml must be main-only and call canonical publication mode"
        )
    if (
        "Required validation gate" not in text
        or "No successful full-validation run" not in text
        or "for event in pull_request merge_group; do" not in text
        or "Required pre-merge validation" not in commit_workflow
    ):
        raise SystemExit(
            "reusable workflow must enforce mode-specific validation and refuse unvalidated publication"
        )
    if "\nconcurrency:\n" in text.split("\njobs:\n", 1)[0]:
        raise SystemExit("concurrency belongs to entry workflows, not the shared reusable workflow")
    if "pull_request_target" in text:
        raise SystemExit("pull_request_target is forbidden")
    missing_typecheck = missing_typecheck_commands(text)
    if missing_typecheck:
        raise SystemExit(
            "canonical workflow is missing standalone blocking type-check commands: "
            + ", ".join(missing_typecheck)
        )
    missing_python_policies = missing_python_policy_commands(text)
    if missing_python_policies:
        raise SystemExit(
            "canonical workflow is missing standalone Python policy commands: "
            + ", ".join(missing_python_policies)
        )
    if PYRIGHT_LEGACY_CONFIG.exists():
        raise SystemExit(
            "duplicate Pyright config must be removed; maintain only pyrightconfig.json"
        )
    try:
        pyright_config = json.loads(PYRIGHT_CONFIG.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SystemExit("pyrightconfig.json must be valid JSON") from error
    if pyright_config.get("typeCheckingMode") != "standard":
        raise SystemExit(
            "pyrightconfig.json must use a standard baseline with a focused strict path list"
        )
    if pyright_config.get("strict") != list(PYRIGHT_EXPECTED_STRICT):
        raise SystemExit("pyrightconfig.json strict paths must match the reviewed core inventory")
    command_lines = {line.strip() for line in text.splitlines()}
    missing_ruff = tuple(command for command in RUFF_COMMANDS if command not in command_lines)
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
            "Pyright coverage inventory changed without an explicit staged update: "
            + ", ".join(coverage_violations)
        )
    if not ty_warnings_are_blocking(TY_CONFIG.read_text(encoding="utf-8")):
        raise SystemExit("ty.toml must set [terminal].error-on-warning = true")
    if re.search(r"\bdocker\s+(run|create|cp)\b", text):
        raise SystemExit("Docker lifecycle belongs in .github/actions/freecad-container")
    if (
        "uses: ./.github/actions/freecad-test" not in text
        and "uses: $/.github/actions/freecad-test" not in text
        and "uses: Uhrendoktor/freecad-cloth/.github/actions/freecad-test@" not in text
    ):
        raise SystemExit("canonical workflow must use freecad-test")
    for path in REQUIRED:
        if not path.is_file():
            raise SystemExit(f"missing required CI component: {path}")
    pbd_action = (ROOT / ".github/actions/pbd-image/action.yml").read_text(encoding="utf-8")
    if (
        "upload-artifact" in pbd_action
        or "docker save" in pbd_action
        or "pbd-validation-image" in pbd_action
    ):
        raise SystemExit("PBD validation image must never be serialized as a workflow artifact")
    container_action = (ROOT / ".github/actions/freecad-container/action.yml").read_text(
        encoding="utf-8"
    )
    if "download-artifact" in container_action or "pbd-validation-image" in container_action:
        raise SystemExit(
            "FreeCAD container action must use GHCR only; workflow image artifacts are forbidden"
        )
    ci_files = [WORKFLOW, *sorted((ROOT / ".github/actions").rglob("action.yml"))]
    for ci_file in ci_files:
        ci_text = ci_file.read_text(encoding="utf-8")
        for match in re.finditer(r"uses:\s+([^\s#]+)", ci_text):
            value = match.group(1)
            if (
                value.startswith("./")
                or value.startswith("$/")
                or value.startswith("Uhrendoktor/freecad-cloth/")
            ):
                continue
            if "@" not in value or not re.fullmatch(
                r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}", value
            ):
                raise SystemExit(f"CI action is not pinned to a full SHA: {ci_file}: {value}")

        for match in re.finditer(r"timeout[^\n]*?\b(\d+)s\b", ci_text):
            if int(match.group(1)) > 180:
                raise SystemExit(
                    f"CI timeout exceeds 180 seconds: {ci_file}: {match.group(0).strip()}"
                )

    if "180s" not in container_action or "timeout-seconds" not in container_action:
        raise SystemExit("FreeCAD container action must retain its 180-second pull contract")
    freecad = (ROOT / ".github/actions/freecad-test/action.yml").read_text(encoding="utf-8")
    if "timeout-seconds:" in freecad:
        raise SystemExit("freecad-test must not define a second application timeout")
    print(f"ci-structure=passed workflow_lines={len(lines)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
