#!/usr/bin/env python3
"""Validate the single authoritative FreeCAD application timeout configuration."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/canonical-execution.yml"
TEST_ACTION = ROOT / ".github/actions/freecad-test/action.yml"
CONTAINER_ACTION = ROOT / ".github/actions/freecad-container/action.yml"
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
    if expected != 120:
        raise SystemExit("FreeCAD application runtime budget must remain at 120 seconds")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    action = TEST_ACTION.read_text(encoding="utf-8")
    container_action = CONTAINER_ACTION.read_text(encoding="utf-8")

    if "freecad_application_timeout_seconds" in workflow:
        raise SystemExit(
            "the canonical workflow must not rewrite the default FreeCAD application budget"
        )
    simulation_ladder = workflow.split("  simulation-ladder:", 1)[1].split("  python:", 1)[0]
    if workflow.count("timeout-seconds:") != 1 or 'timeout-seconds: "360"' not in simulation_ladder:
        raise SystemExit(
            "only the cube simulation ladder may request the explicit 360-second runtime override"
        )
    if (
        'default: "120"' not in action
        or "timeout-seconds: ${{ inputs.timeout-seconds }}" not in action
    ):
        raise SystemExit(
            "FreeCAD test action must pass its default-120 timeout through to the container"
        )
    if "FREECAD_APPLICATION_TIMEOUT_SECONDS=" not in action:
        raise SystemExit(
            "FreeCAD test action must pass non-default runtime overrides to run_freecad.py"
        )
    if 'default: "120"' not in container_action or "maximum 360 seconds" not in container_action:
        raise SystemExit("FreeCAD container must default to 120 seconds and cap overrides at 360")
    if 'if [ "$timeout_seconds" -gt 360 ]; then' not in container_action:
        raise SystemExit("FreeCAD container action must enforce the 360-second absolute cap")
    run_freecad = (ROOT / "tools/ci/run_freecad.py").read_text(encoding="utf-8")
    if "def configured_timeout_seconds()" not in run_freecad:
        raise SystemExit("run_freecad.py does not expose the authoritative timeout reader")
    if "timeout_seconds = configured_timeout_seconds()" not in run_freecad:
        raise SystemExit("run_freecad.py does not consume the authoritative application timeout")
    if "FREECAD_APPLICATION_TIMEOUT_SECONDS" not in run_freecad:
        raise SystemExit("run_freecad.py does not validate the scoped runtime override")

    print(f"timeout-authority={expected}s source=pyproject.toml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
