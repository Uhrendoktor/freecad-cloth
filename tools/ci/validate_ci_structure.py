"""Validate the repository CI structure and hard runtime contracts."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/canonical-execution.yml"
PYRIGHT_CONFIG = ROOT / "pyrightconfig.json"
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
    "freecad_cloth/sewing/SeamGraph.py",
    "freecad_cloth/sewing/SewingCorrespondence.py",
    "freecad_cloth/simulation/ClothBackend.py",
    "freecad_cloth/simulation/ClothSolver.py",
    "freecad_cloth/simulation/DrapeTarget.py",
    "freecad_cloth/simulation/SimulationQuality.py",
    "freecad_cloth/simulation/SimulationObjects.py",
    "freecad_cloth/simulation/SimulationQualityRuntime.py",
    "freecad_cloth/simulation/PositionBasedDynamicsBackend.py",
)
PYRIGHT_EXPECTED_EXCLUDE = (
    "**/*Gui.py",
    "**/*Commands.py",
    "**/workbench.py",
)

TYPECHECK_COMMANDS = (
    "python tools/ci/check_explicit_any_annotations.py",
    "pyright -p pyrightconfig.json",
    "pyright -p pyrightconfig.agent-strict.json",
    "ty check --output-format github freecad_cloth/simulation/DrapeFailureClassifier.py freecad_cloth/simulation/ClothBackend.py freecad_cloth/simulation/ClothSolver.py",
    "python tools/ci/check_changed_python_types.py",
)


def missing_typecheck_commands(workflow_text: str) -> tuple[str, ...]:
    """Return required blocking type gates not present as standalone shell commands.

    Exact-line matching is intentional: a failing command inside an AND chain
    can be exempt from Bash errexit handling, allowing CI to continue.
    """
    command_lines = {line.strip() for line in workflow_text.splitlines()}
    return tuple(command for command in TYPECHECK_COMMANDS if command not in command_lines)


def pyright_coverage_contract_violations(config_text: str) -> tuple[str, ...]:
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
    return tuple(f"<Pyright inventory path does not exist: {path}>" for path in missing_paths)


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
    files = sorted((ROOT / ".github/workflows").glob("*.y*ml"))
    if files != [WORKFLOW]:
        raise SystemExit(f"expected exactly one canonical workflow, found: {files}")
    text = WORKFLOW.read_text(encoding="utf-8")
    lines = text.splitlines()
    if len(lines) > 600:
        raise SystemExit(f"canonical workflow is {len(lines)} lines; limit is 600")
    if "pull_request_target" in text:
        raise SystemExit("pull_request_target is forbidden")
    missing_typecheck = missing_typecheck_commands(text)
    if missing_typecheck:
        raise SystemExit(
            "canonical workflow is missing standalone blocking type-check commands: "
            + ", ".join(missing_typecheck)
        )
    coverage_violations = pyright_coverage_contract_violations(
        PYRIGHT_CONFIG.read_text(encoding="utf-8")
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
