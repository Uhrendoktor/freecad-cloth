# Copyright (C) 2026 FreeCAD Cloth contributors
"""Run external commands through an explicit-argument, shell-free process boundary."""

from __future__ import annotations

import asyncio
import os
import shutil
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from os import PathLike


@dataclass(frozen=True, slots=True)
class CommandOptions:
    """Optional execution controls shared by repository CI command callers.

    Attributes:
        cwd: Working directory inherited by the child process.
        env: Complete child environment mapping, or None to inherit the parent.
        check: Whether an unsuccessful exit status should raise a command error.
        capture_output: Whether stdout and stderr should be captured as text.
        timeout: Maximum runtime in seconds, or None for an unbounded process.
    """

    cwd: str | PathLike[str] | None = None
    env: Mapping[str, str] | None = None
    check: bool = True
    capture_output: bool = False
    timeout: float | None = None


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Completed process result with optional captured text streams.

    Attributes:
        args: Resolved executable path followed by the exact argument vector.
        returncode: Exit status reported by the operating system.
        stdout: Captured standard output, or None when output was inherited.
        stderr: Captured standard error, or None when output was inherited.
    """

    args: tuple[str, ...]
    returncode: int
    stdout: str | None
    stderr: str | None


class CommandExecutionError(RuntimeError):
    """Raised when a checked command exits unsuccessfully or cannot run synchronously."""


class CommandTimeoutError(TimeoutError):
    """Raised when an external process exceeds its configured runtime limit."""

    def __init__(self, executable: str, timeout: float) -> None:
        """Initialize the timeout error for one executable.

        Args:
            executable: Resolved executable that exceeded its time budget.
            timeout: Maximum runtime in seconds that was exceeded.
        """
        super().__init__(f"Command exceeded its {timeout:g}-second timeout: {executable}")


async def _execute(args: tuple[str, ...], options: CommandOptions) -> CommandResult:
    """Start one executable directly and await its completion.

    Args:
        args: Absolute executable path and its explicit argument vector.
        options: Execution settings for working directory, environment, capture, and timeout.

    Returns:
        Exit status and captured streams for the completed process.

    Raises:
        CommandTimeoutError: If the process does not finish before its configured timeout.
        CommandExecutionError: If a timed-out process has no configured timeout value.
        RuntimeError: If the child process does not report a terminal exit status.
    """
    pipe = asyncio.subprocess.PIPE if options.capture_output else None
    process = await asyncio.create_subprocess_exec(
        *args,
        cwd=options.cwd,
        env=dict(options.env) if options.env is not None else None,
        stdout=pipe,
        stderr=pipe,
    )
    try:
        async with asyncio.timeout(options.timeout):
            stdout_bytes, stderr_bytes = await process.communicate()
    except TimeoutError as exc:
        if process.returncode is None:
            process.kill()
            await process.wait()
        if options.timeout is None:
            msg = f"Command timed out without a configured limit: {args[0]}"
            raise CommandExecutionError(msg) from exc
        raise CommandTimeoutError(args[0], options.timeout) from exc

    if process.returncode is None:
        msg = f"Process did not report an exit status: {args[0]}"
        raise RuntimeError(msg)
    return CommandResult(
        args=args,
        returncode=process.returncode,
        stdout=stdout_bytes.decode("utf-8", errors="replace") if options.capture_output else None,
        stderr=stderr_bytes.decode("utf-8", errors="replace") if options.capture_output else None,
    )


def run_command(
    args: Sequence[str | PathLike[str]],
    *,
    options: CommandOptions | None = None,
) -> CommandResult:
    """Run an executable directly, without a shell or interpolated command string.

    Args:
        args: Executable name/path followed by discrete command-line arguments.
        options: Optional working directory, environment, output capture, status, and timeout.

    Returns:
        Process result containing the resolved argument vector, exit status, and optional
        captured output streams.

    Raises:
        ValueError: If the argument vector is empty or the configured timeout is not positive.
        FileNotFoundError: If the requested executable cannot be resolved on PATH.
        CommandTimeoutError: If the command exceeds its runtime limit; the child is terminated.
        CommandExecutionError: If a checked process fails or a running event loop prevents
            synchronous execution.
    """
    if not args:
        msg = "an executable command is required"
        raise ValueError(msg)
    execution = options if options is not None else CommandOptions()
    if execution.timeout is not None and execution.timeout <= 0:
        msg = "command timeout must be positive"
        raise ValueError(msg)

    unresolved_args = tuple(os.fspath(argument) for argument in args)
    executable = shutil.which(unresolved_args[0])
    if executable is None:
        msg = f"Required executable is not on PATH: {unresolved_args[0]}"
        raise FileNotFoundError(msg)
    resolved_args = (executable, *unresolved_args[1:])
    try:
        result = asyncio.run(_execute(resolved_args, execution))
    except CommandTimeoutError:
        raise
    except RuntimeError as exc:
        msg = "Synchronous command execution cannot run inside an active event loop"
        raise CommandExecutionError(msg) from exc
    if execution.check and result.returncode != 0:
        detail = result.stderr or result.stdout or "no diagnostic output"
        msg = f"Command exited with code {result.returncode}: {resolved_args[0]}\n{detail}"
        raise CommandExecutionError(msg)
    return result
