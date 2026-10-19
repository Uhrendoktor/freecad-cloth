# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression tests for canonical workflow Ruff command validation."""

from unittest import TestCase

from tools.ci.validate_ci_structure import RUFF_COMMANDS, missing_ruff_commands


class RuffWorkflowCommandContractTests(TestCase):
    """Verify the static checker recognizes only standalone Ruff commands."""

    def test_inline_run_field_is_a_standalone_command(self) -> None:
        """Accept simple YAML run fields and multiline shell commands."""
        workflow = f"run: {RUFF_COMMANDS[0]}\n{RUFF_COMMANDS[1]}\n"
        self.assertEqual(missing_ruff_commands(workflow), ())

    def test_and_chained_command_is_not_a_standalone_command(self) -> None:
        """Reject a Ruff command chained with another shell expression."""
        workflow = f"run: {RUFF_COMMANDS[0]} && true\n{RUFF_COMMANDS[1]}\n"
        self.assertEqual(missing_ruff_commands(workflow), (RUFF_COMMANDS[0],))
