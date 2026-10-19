# Copyright (C) 2026 FreeCAD Cloth contributors
"""Run external executables directly without invoking a command shell."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass

SUCCESS_EXIT_CODE = 0
MINIMUM_TIMEOUT_SECONDS = 0.0


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Store the exit status and captured text output of an external command."""

    returncode: int
    stdout: str
    stderr: str


class CommandExecutionError(RuntimeError):
    """Describe an external command that exited unsuccessfully."""

    def __init__(
        self,
        command: tuple[str, ...],
        returncode: int,
        stdout: str,
        stderr: str,
    ) -> None:
        """Initialize the failed command result.

        Args:
            command: Executable path and arguments passed to the child process.
            returncode: Non-zero status reported by the child process.
            stdout: Standard output captured from the child process.
            stderr: Standard error captured from the child process.
        """
        self.command = command
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        msg = f"Command {list(command)!r} returned non-zero exit status {returncode}."
        super().__init__(msg)


class CommandTimeoutError(TimeoutError):
    """Describe an external command that exceeded its allowed runtime."""

    def __init__(
        self,
        command: tuple[str, ...],
        timeout: float,
        stdout: str,
        stderr: str,
    ) -> None:
        """Initialize the timed-out command result.

        Args:
            command: Executable path and arguments passed to the child process.
            timeout: Maximum runtime in seconds configured for the command.
            stdout: Standard output captured before termination.
            stderr: Standard error captured before termination.
        """
        self.command = command
        self.timeout = timeout
        self.stdout = stdout
        self.stderr = stderr
        msg = f"Command {list(command)!r} timed out after {timeout} seconds."
        super().__init__(msg)


async def _run_async(
    command: tuple[str, ...],
    *,
    capture_output: bool,
    timeout: float | None,
) -> CommandResult:
    """Execute an argument vector and collect output when requested.

    Args:
        command: Executable path and arguments passed to the child process.
        capture_output: Whether to capture both standard output and standard error.
        timeout: Maximum runtime in seconds, or None to wait without a deadline.

    Returns:
        Exit status and captured output from the child process.

    Raises:
        CommandTimeoutError: If the process does not finish within its timeout.
        RuntimeError: If the process API does not report an exit status.
    """
    output_target = asyncio.subprocess.PIPE if capture_output else None
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=output_target,
        stderr=output_target,
    )
    try:
        if timeout is None:
            stdout, stderr = await process.communicate()
        else:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout)
    except TimeoutError as exc:
        process.kill()
        stdout, stderr = await process.communicate()
        stdout_text = stdout.decode("utf-8", errors="replace") if stdout is not None else ""
        stderr_text = stderr.decode("utf-8", errors="replace") if stderr is not None else ""
        raise CommandTimeoutError(command, timeout, stdout_text, stderr_text) from exc

    if process.returncode is None:
        msg = f"Command {list(command)!r} ended without an exit status."
        raise RuntimeError(msg)
    stdout_text = stdout.decode("utf-8", errors="replace") if stdout is not None else ""
    stderr_text = stderr.decode("utf-8", errors="replace") if stderr is not None else ""
    return CommandResult(process.returncode, stdout_text, stderr_text)


def run_command(
    command: Sequence[str],
    *,
    capture_output: bool = False,
    timeout: float | None = None,
    check: bool = True,
) -> CommandResult:
    """Run an external executable with no shell interpolation.

    Args:
        command: Non-empty executable path and its separate command-line arguments.
        capture_output: Whether to collect stdout and stderr instead of inheriting them.
        timeout: Maximum runtime in seconds, or None to wait without a deadline.
        check: Whether a non-zero exit status should raise CommandExecutionError.

    Returns:
        Child exit status and any captured text output.

    Raises:
        TypeError: If a command argument is not a string.
        ValueError: If the argument vector is empty, includes a null byte, or the timeout is invalid.
        CommandExecutionError: If check is true and the child exits unsuccessfully.
        CommandTimeoutError: If the child exceeds its timeout.
        OSError: If the operating system cannot start the executable.
    """
    arguments = tuple(command)
    if not arguments:
        msg = "command argument vector must not be empty"
        raise ValueError(msg)
    if any(not isinstance(argument, str) for argument in arguments):
        msg = "all command arguments must be strings"
        raise TypeError(msg)
    if any("\x00" in argument for argument in arguments):
        msg = "command arguments must not contain null bytes"
        raise ValueError(msg)
    if timeout is not None and timeout <= MINIMUM_TIMEOUT_SECONDS:
        msg = f"command timeout must be positive, got {timeout}"
        raise ValueError(msg)

    result = asyncio.run(
        _run_async(arguments, capture_output=capture_output, timeout=timeout)
    )
    if check and result.returncode != SUCCESS_EXIT_CODE:
        raise CommandExecutionError(
            arguments,
            result.returncode,
            result.stdout,
            result.stderr,
        )
    return result
