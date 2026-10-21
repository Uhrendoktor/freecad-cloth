# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression tests for canonical workflow Ruff command validation."""

import pytest

from tools.ci.validate_ci_structure import RUFF_COMMANDS, missing_ruff_commands


def test_inline_run_field_is_a_standalone_command() -> None:
    """Accept simple YAML run fields and multiline shell commands."""
    workflow = f"run: {RUFF_COMMANDS[0]}\n{RUFF_COMMANDS[1]}\n"
    missing = missing_ruff_commands(workflow)
    if missing:
        pytest.fail(f"Expected both Ruff commands to be recognized, found {missing}.")


def test_and_chained_command_is_not_a_standalone_command() -> None:
    """Reject a Ruff command chained with another shell expression."""
    workflow = f"run: {RUFF_COMMANDS[0]} && true\n{RUFF_COMMANDS[1]}\n"
    missing = missing_ruff_commands(workflow)
    if missing != (RUFF_COMMANDS[0],):
        pytest.fail(f"Expected only the chained command to be missing, found {missing}.")
