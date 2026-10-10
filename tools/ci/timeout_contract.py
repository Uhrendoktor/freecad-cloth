#!/usr/bin/env python3
"""Validate the single authoritative FreeCAD application timeout configuration."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/canonical-execution.yml"
TEST_ACTION = ROOT / ".github/actions/freecad-test/action.yml"
PYPROJECT = ROOT / "pyproject.toml"


def configured_timeout() -> int:
    """Return the authoritative FreeCAD application timeout from pyproject.toml."""
    import tomllib

    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    value = (
        data.get("tool", {})
        .get("freecad_cloth", {})
        .get("ci", {})
        .get("freecad_application_timeout_seconds")
    )
    if not isinstance(value, int) or value <= 0:
        raise ValueError(
            "[tool.freecad_cloth.ci].freecad_application_timeout_seconds must be a positive integer"
        )
    return value


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
        raise SystemExit("FreeCAD test action must not define a second application timeout")
    run_freecad = (ROOT / "tools/ci/run_freecad.py").read_text(encoding="utf-8")
    if "def configured_timeout_seconds()" not in run_freecad:
        raise SystemExit("run_freecad.py does not expose the authoritative timeout reader")
    if "timeout_seconds = configured_timeout_seconds()" not in run_freecad:
        raise SystemExit("run_freecad.py does not consume the authoritative application timeout")

    print(f"timeout-authority={expected}s source=pyproject.toml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
