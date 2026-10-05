"""Validate the repository CI structure and hard runtime contracts."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/canonical-execution.yml"
REQUIRED = (
    ROOT / ".github/actions/freecad-test/action.yml",
    ROOT / ".github/actions/freecad-container/action.yml",
    ROOT / ".github/actions/publish-visual-evidence/action.yml",
    ROOT / "tools/ci/run_freecad.py",
    ROOT / "tools/ci/validate_manifests.py",
    ROOT / "tools/ci/visual_evidence.py",
)


def main() -> int:
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
    for match in re.finditer(r"uses:\s+([^\s#]+)", text):
        value = match.group(1)
        if value.startswith("./"):
            continue
        if "@" not in value or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}", value):
            raise SystemExit(f"workflow action is not pinned to a full SHA: {value}")
    for path in (
        ROOT / ".github/actions/freecad-container/action.yml",
        ROOT / ".github/actions/freecad-test/action.yml",
    ):
        action = path.read_text(encoding="utf-8")
        if "timeout-seconds" not in action or "60s" not in action:
            raise SystemExit(f"60-second runtime contract missing from {path}")
    print(f"ci-structure=passed workflow_lines={len(lines)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
