"""Validate the repository CI structure and hard runtime contracts."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/canonical-execution.yml"
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


TYPECHECK_COMMANDS = (
    "python tools/ci/check_explicit_any_annotations.py",
    "pyright -p pyrightconfig.json",
    "pyright -p pyrightconfig.agent-strict.json",
    "ty check --output-format github freecad_cloth/simulation/DrapeFailureClassifier.py freecad_cloth/simulation/ClothBackend.py freecad_cloth/simulation/ClothSolver.py",
)


def missing_typecheck_commands(workflow_text: str) -> tuple[str, ...]:
    """Return required blocking type-gate commands missing from the canonical workflow."""
    return tuple(command for command in TYPECHECK_COMMANDS if command not in workflow_text)


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
            "canonical workflow is missing required type-check gates: "
            + ", ".join(missing_typecheck)
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
