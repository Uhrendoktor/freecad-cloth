#!/usr/bin/env python3
"""Validate the single authoritative FreeCAD application timeout configuration."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.ci.run_freecad import configured_timeout_seconds
WORKFLOW = ROOT / ".github/workflows/canonical-execution.yml"
TEST_ACTION = ROOT / ".github/actions/freecad-test/action.yml"
PYPROJECT = ROOT / "pyproject.toml"


def configured_timeout() -> int:
    """Return the authoritative FreeCAD application timeout from run_freecad.py."""
    return int(configured_timeout_seconds())


def main() -> int:
    """Validate that workflow and action surfaces do not define a second timeout."""
    expected = configured_timeout()
    workflow = WORKFLOW.read_text(encoding="utf-8")
    action = TEST_ACTION.read_text(encoding="utf-8")

    if "timeout-seconds:" in workflow:
        raise SystemExit(
            "FreeCAD application timeout must not be duplicated in the canonical workflow"
        )
    if "timeout-seconds:" in action:
        raise SystemExit(
            "FreeCAD test action must not define a second application timeout"
        )
    run_freecad = (ROOT / "tools/ci/run_freecad.py").read_text(encoding="utf-8")
    if "def configured_timeout_seconds()" not in run_freecad:
        raise SystemExit("run_freecad.py does not expose the authoritative timeout reader")
    if "timeout_seconds = configured_timeout_seconds()" not in run_freecad:
        raise SystemExit("run_freecad.py does not consume the authoritative application timeout")

    print(f"timeout-authority={expected}s source=pyproject.toml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
