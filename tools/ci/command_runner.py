# Copyright (C) 2026 FreeCAD Cloth contributors
"""Run external commands through an explicit-argument, shell-free process boundary."""

from __future__ import annotations

import asyncio
import os
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from os import PathLike


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Completed process result with optional captured text streams.

    Args:
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
    """Raised when a command requested with check=True exits unsuccessfully."""


async def _execute(
    args: tuple[str, ...],
    *,
    cwd: str | PathLike[str] | None,
    env: Mapping[str, str] | None,
    capture_output: bool,
    timeout: float | None,
) -> CommandResult:
    """Start one executable directly and await its completion.

    Args:
        args: Absolute executable path and its explicit argument vector.
        cwd: Optional working directory inherited by the child process.
        env: Optional complete child environment mapping.
        capture_output: Whether stdout and stderr should be captured as text.
        timeout: Maximum execution duration in seconds, or None for no limit.

    Returns:
        Exit status and captured streams for the completed process.

    Raises:
        TimeoutError: If the process does not finish before the requested timeout.
    """
    pipe = asyncio.subprocess.PIPE if capture_output else None
    process = await asyncio.create_subprocess_exec(
        *args,
        cwd=cwd,
        env=dict(env) if env is not None else None,
        stdout=pipe,
        stderr=pipe,
    )
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except TimeoutError as exc:
        if process.returncode is None:
            process.kill()
            await process.wait()
        raise TimeoutError(f"Command exceeded its {timeout:g}-second timeout: {args[0]}") from exc

    if process.returncode is None:
        msg = f"Process did not report an exit status: {args[0]}"
        raise RuntimeError(msg)
    return CommandResult(
        args=args,
        returncode=process.returncode,
        stdout=stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes is not None else None,
        stderr=stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes is not None else None,
    )


def run_command(
    args: Sequence[str | PathLike[str]],
    *,
    cwd: str | PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
    check: bool = True,
    capture_output: bool = False,
    timeout: float | None = None,
) -> CommandResult:
    """Run an executable directly, without a shell or interpolated command string.

    Args:
        args: Executable name/path followed by discrete command-line arguments.
        cwd: Optional working directory for the command.
        env: Optional environment mapping replacing the inherited child environment.
        check: Whether a nonzero exit code should raise CommandExecutionError.
        capture_output: Whether to capture stdout and stderr as decoded text.
        timeout: Maximum runtime in seconds, or None when the command is unbounded.

    Returns:
        Process result containing the resolved argument vector, exit status, and optional
        captured output streams.

    Raises:
        ValueError: If the argument vector is empty or timeout is not positive.
        FileNotFoundError: If the requested executable cannot be resolved on PATH.
        TimeoutError: If the command exceeds its runtime limit; the child is terminated.
        CommandExecutionError: If check is true and the process exits with a nonzero status.
        RuntimeError: If called while another asyncio event loop is already running.
    """
    if not args:
        msg = "an executable command is required"
        raise ValueError(msg)
    if timeout is not None and timeout <= 0:
        msg = "command timeout must be positive"
        raise ValueError(msg)

    unresolved_args = tuple(os.fspath(argument) for argument in args)
    executable = shutil.which(unresolved_args[0])
    if executable is None:
        msg = f"Required executable is not on PATH: {unresolved_args[0]}"
        raise FileNotFoundError(msg)
    resolved_args = (executable, *unresolved_args[1:])
    result = asyncio.run(
        _execute(
            resolved_args,
            cwd=cwd,
            env=env,
            capture_output=capture_output,
            timeout=timeout,
        )
    )
    if check and result.returncode != 0:
        detail = result.stderr or result.stdout or "no diagnostic output"
        msg = f"Command exited with code {result.returncode}: {resolved_args[0]}\n{detail}"
        raise CommandExecutionError(msg)
    return result
