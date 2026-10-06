"""Validate the repository CI structure and hard runtime contracts."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/canonical-execution.yml"
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
)


def main() -> int:
    """Validate the repository CI structure and hard runtime contracts."""
    files = sorted((ROOT / ".github/workflows").glob("*.y*ml"))
    if files != [WORKFLOW]:
        raise SystemExit(f"expected exactly one canonical workflow, found: {files}")
    text = WORKFLOW.read_text(encoding="utf-8")
    lines = text.splitlines()
    if len(lines) > 500:
        raise SystemExit(f"canonical workflow is {len(lines)} lines; limit is 500")
    if "pull_request_target" in text:
        raise SystemExit("pull_request_target is forbidden")
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

    for index, line in enumerate(text.splitlines()):
        if (
            "uses: ./.github/actions/freecad-test" not in line
            and "uses: $/.github/actions/freecad-test" not in line
            and "uses: Uhrendoktor/freecad-cloth/.github/actions/freecad-test@" not in line
        ):
            continue
        step = []
        for candidate in text.splitlines()[index + 1 :]:
            if candidate.startswith("      - "):
                break
            step.append(candidate)
        match = re.search(r'timeout-seconds:\s*"?(\d+)"?', "\n".join(step))
        if not match or int(match.group(1)) > 120:
            raise SystemExit("every FreeCAD test action must declare a timeout <=120 seconds")
    if "180s" not in container_action or "timeout-seconds" not in container_action:
        raise SystemExit("FreeCAD container action must retain its 180-second pull contract")
    freecad = (ROOT / ".github/actions/freecad-test/action.yml").read_text(encoding="utf-8")
    if (
        'default: "120"' not in freecad
        or "maximum 120 seconds" not in freecad
        or "60s" not in freecad
        or "timeout-seconds" not in freecad
    ):
        raise SystemExit(
            "FreeCAD test action must retain its 120-second runtime and 60-second preflight contracts"
        )
    print(f"ci-structure=passed workflow_lines={len(lines)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
