# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression tests for the shell-free CI command execution boundary."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from tests.support.assertions import require
from tools.ci.command_runner import CommandExecutionError, CommandOptions, run_command

COMMAND_FAILURE_EXIT_CODE = 7
COMMAND_TIMEOUT_SECONDS = 0.05
EXPECTED_STDOUT = "command-runner-ok\n"
MISSING_EXECUTABLE = Path("/missing/cloth-command-runner")


def _python_executable() -> str:
    """Return the Python executable used by the active test interpreter.

    Returns:
        Absolute path to the current Python interpreter.

    Raises:
        RuntimeError: If the interpreter does not expose an executable path.
    """
    if sys.executable is None:
        msg = "Python executable path is unavailable"
        raise RuntimeError(msg)
    return sys.executable


def test_run_command_captures_standard_output_and_error() -> None:
    """Capture decoded output streams from a successful direct child process."""
    result = run_command(
        [_python_executable(), "-c", "print('command-runner-ok')"],
        options=CommandOptions(capture_output=True, check=True),
    )

    require(
        condition=result.returncode == 0,
        message="Successful command must return a zero exit status.",
    )
    require(
        condition=result.stdout == EXPECTED_STDOUT,
        message="Captured standard output must preserve emitted text.",
    )
    require(
        condition=result.stderr == "",
        message="Successful command must expose an empty captured standard-error stream.",
    )


def test_run_command_returns_nonzero_status_when_check_is_disabled() -> None:
    """Return a failing exit status without raising when check=False."""
    result = run_command(
        [_python_executable(), "-c", f"raise SystemExit({COMMAND_FAILURE_EXIT_CODE})"],
        options=CommandOptions(check=False, capture_output=True),
    )

    require(
        condition=result.returncode == COMMAND_FAILURE_EXIT_CODE,
        message="Unchecked command must preserve its nonzero process exit status.",
    )


def test_run_command_raises_for_a_failing_checked_process() -> None:
    """Raise the typed command error when a checked child exits unsuccessfully."""
    with pytest.raises(CommandExecutionError, match=f"exit code {COMMAND_FAILURE_EXIT_CODE}"):
        run_command(
            [_python_executable(), "-c", f"raise SystemExit({COMMAND_FAILURE_EXIT_CODE})"],
            options=CommandOptions(capture_output=True),
        )


def test_run_command_rejects_empty_argument_vectors() -> None:
    """Reject an empty command before creating an operating-system process."""
    empty_args: tuple[str, ...] = ()
    with pytest.raises(ValueError, match="executable command is required"):
        run_command(empty_args)


def test_run_command_rejects_missing_executable_paths() -> None:
    """Reject an absolute executable path that does not exist."""
    with pytest.raises(FileNotFoundError, match="not on PATH"):
        run_command([MISSING_EXECUTABLE])


def test_run_command_terminates_a_child_that_exceeds_its_timeout() -> None:
    """Terminate a child process that does not finish within its runtime budget."""
    with pytest.raises(TimeoutError, match="exceeded its"):
        run_command(
            [_python_executable(), "-c", "import time; time.sleep(1)"],
            options=CommandOptions(timeout=COMMAND_TIMEOUT_SECONDS),
        )
