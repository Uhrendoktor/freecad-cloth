# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression tests for documentation GIF assembly command options."""

from __future__ import annotations

from collections.abc import Sequence
from os import PathLike
from pathlib import Path

import pytest

from tools.ci import build_visual_gifs
from tools.ci.command_runner import CommandOptions, CommandResult


def test_build_visual_gif_passes_checked_command_options(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pass the command-runner options through its supported API.

    Args:
        tmp_path: Temporary directory for a synthetic input frame and GIF output.
        monkeypatch: Pytest fixture used to replace the external process boundary.
    """
    frame = tmp_path / "frame-000.png"
    frame.write_bytes(b"synthetic frame")
    output = tmp_path / "generated.gif"
    calls: list[tuple[tuple[str, ...], CommandOptions | None]] = []

    def fake_run_command(
        args: Sequence[str | PathLike[str]],
        *,
        options: CommandOptions | None = None,
    ) -> CommandResult:
        """Record the process request and emulate a non-empty GIF result.

        Args:
            args: Executable and arguments supplied by the GIF builder.
            options: Typed command execution settings supplied by the caller.

        Returns:
            Successful command result with inherited output streams.
        """
        command = tuple(str(argument) for argument in args)
        calls.append((command, options))
        output.write_bytes(b"GIF89a")
        return CommandResult(args=command, returncode=0, stdout=None, stderr=None)

    monkeypatch.setattr(build_visual_gifs, "run_command", fake_run_command)

    build_visual_gifs.build("magick", [frame], output, "8", timeout=23)

    expected_command = (
        "magick",
        "-delay",
        "8",
        "-loop",
        "0",
        str(frame),
        "-colors",
        "128",
        str(output),
    )
    assert calls == [(expected_command, CommandOptions(check=True, timeout=23))], (
        "GIF assembly must pass checked execution and its timeout through CommandOptions."
    )
    assert output.is_file() and output.read_bytes() == b"GIF89a", (
        "GIF assembly should accept a non-empty output from the command runner."
    )
