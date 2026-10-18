#!/usr/bin/env python3
# Copyright (C) 2026 FreeCAD Cloth contributors
"""Validate the single authoritative FreeCAD application timeout configuration."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

try:
    from freecad_timeout_config import read_application_timeout
except ModuleNotFoundError:
    from tools.ci.freecad_timeout_config import read_application_timeout

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/canonical-execution.yml"
TEST_ACTION = ROOT / ".github/actions/freecad-test/action.yml"
CONTAINER_ACTION = ROOT / ".github/actions/freecad-container/action.yml"
PYPROJECT = ROOT / "pyproject.toml"
EXPECTED_TIMEOUT_SECONDS: Final = 120


def configured_timeout() -> int:
    """Read the authoritative FreeCAD application timeout from pyproject.toml.

    Returns:
        Positive application timeout in seconds.
    """
    return read_application_timeout(PYPROJECT)


def _require_contract(condition: bool, message: str) -> None:
    """Raise a process-level error when a timeout contract condition is false.

    Args:
        condition: Boolean result that the timeout contract requires to be true.
        message: Explanation displayed when the required condition is false.

    Raises:
        SystemExit: If the supplied condition does not satisfy the contract.
    """
    if not condition:
        raise SystemExit(message)


def main() -> int:
    """Validate that workflow and action surfaces do not define a second timeout.

    Returns:
        Process status indicating whether the timeout contract is valid.
    """
    expected = configured_timeout()
    _require_contract(
        expected == EXPECTED_TIMEOUT_SECONDS,
        "FreeCAD application runtime budget must remain at 120 seconds",
    )
    workflow = WORKFLOW.read_text(encoding="utf-8")
    action = TEST_ACTION.read_text(encoding="utf-8")
    container_action = CONTAINER_ACTION.read_text(encoding="utf-8")

    _require_contract(
        "freecad_application_timeout_seconds" not in workflow,
        "the canonical workflow must not rewrite the default FreeCAD application budget",
    )
    simulation_ladder = workflow.split("  simulation-ladder:", 1)[1].split("  python:", 1)[0]
    _require_contract(
        workflow.count("timeout-seconds:") == 1
        and 'timeout-seconds: "360"' in simulation_ladder,
        "only the cube simulation ladder may request the explicit 360-second runtime override",
    )
    _require_contract(
        'default: "120"' in action
        and "timeout-seconds: ${{ inputs.timeout-seconds }}" in action,
        "FreeCAD test action must pass its default-120 timeout through to the container",
    )
    _require_contract(
        "FREECAD_APPLICATION_TIMEOUT_SECONDS=" in action,
        "FreeCAD test action must pass non-default runtime overrides to run_freecad.py",
    )
    _require_contract(
        'default: "120"' in container_action and "maximum 360 seconds" in container_action,
        "FreeCAD container must default to 120 seconds and cap overrides at 360",
    )
    _require_contract(
        'if [ "$timeout_seconds" -gt 360 ]; then' in container_action,
        "FreeCAD container action must enforce the 360-second absolute cap",
    )
    run_freecad = (ROOT / "tools/ci/run_freecad.py").read_text(encoding="utf-8")
    _require_contract(
        "def configured_timeout_seconds()" in run_freecad,
        "run_freecad.py does not expose the authoritative timeout reader",
    )
    _require_contract(
        "timeout_seconds = configured_timeout_seconds()" in run_freecad,
        "run_freecad.py does not consume the authoritative application timeout",
    )
    _require_contract(
        "FREECAD_APPLICATION_TIMEOUT_SECONDS" in run_freecad,
        "run_freecad.py does not validate the scoped runtime override",
    )

    sys.stdout.write(f"timeout-authority={expected}s source=pyproject.toml\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
