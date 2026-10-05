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
)


def main() -> int:
    """Validate the repository CI structure and hard runtime contracts."""
    files = sorted((ROOT / ".github/workflows").glob("*.y*ml"))
    if files != [WORKFLOW]:
        raise SystemExit(f"expected exactly one canonical workflow, found: {files}")
    text = WORKFLOW.read_text(encoding="utf-8")
    lines = text.splitlines()
    if len(lines) > 450:
        raise SystemExit(f"canonical workflow is {len(lines)} lines; limit is 450")
    if "pull_request_target" in text:
        raise SystemExit("pull_request_target is forbidden")
    if re.search(r"\bdocker\s+(run|create|cp)\b", text):
        raise SystemExit("Docker lifecycle belongs in .github/actions/freecad-container")
    if "freecad-test/action.yml" not in text:
        raise SystemExit("canonical workflow must use freecad-test")
    for path in REQUIRED:
        if not path.is_file():
            raise SystemExit(f"missing required CI component: {path}")
    ci_files = [WORKFLOW, *sorted((ROOT / ".github/actions").rglob("action.yml"))]
    for ci_file in ci_files:
        ci_text = ci_file.read_text(encoding="utf-8")
        for match in re.finditer(r"uses:\s+([^\s#]+)", ci_text):
            value = match.group(1)
            if value.startswith("./"):
                continue
            if "@" not in value or not re.fullmatch(
                r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}", value
            ):
                raise SystemExit(
                    f"CI action is not pinned to a full SHA: {ci_file}: {value}"
                )

        for match in re.finditer(r"timeout[^\n]*?\b(\d+)s\b", ci_text):
            if int(match.group(1)) > 60:
                raise SystemExit(
                    f"CI timeout exceeds 60 seconds: {ci_file}: {match.group(0).strip()}"
                )

    for index, line in enumerate(text.splitlines()):
        if "uses: ./.github/actions/freecad-test" not in line:
            continue
        step = []
        for candidate in text.splitlines()[index + 1 :]:
            if candidate.startswith("      - "):
                break
            step.append(candidate)
        match = re.search(r'timeout-seconds:\s*"?(\d+)"?', "\n".join(step))
        if not match or int(match.group(1)) > 55:
            raise SystemExit("every FreeCAD test action must declare a timeout <=55 seconds")
    for path in (
        ROOT / ".github/actions/freecad-container/action.yml",
        ROOT / ".github/actions/freecad-test/action.yml",
    ):
        action = path.read_text(encoding="utf-8")
        if "60s" not in action or "timeout-seconds" not in action:
            raise SystemExit(f"60-second runtime contract missing from {path}")
    freecad = (ROOT / ".github/actions/freecad-test/action.yml").read_text(encoding="utf-8")
    if 'default: "55"' not in freecad or "maximum 55 seconds" not in freecad:
        raise SystemExit("FreeCAD test action must default to a 55-second maximum")
    print(f"ci-structure=passed workflow_lines={len(lines)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
