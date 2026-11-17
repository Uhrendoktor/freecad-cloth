# Copyright (C) 2026 FreeCAD Cloth contributors
"""Tests for bounded ImageMagick invocation in the documentation GIF builder."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tools.ci import build_visual_gifs
from tools.ci.command_runner import CommandOptions, CommandResult

if TYPE_CHECKING:
    from os import PathLike


def test_build_uses_shared_command_options_and_checks_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pass timeout/status through CommandOptions and require a generated GIF."""
    frame = tmp_path / "frame.png"
    frame.write_bytes(b"frame")
    output = tmp_path / "animation.gif"
    calls: list[tuple[tuple[str, ...], CommandOptions | None]] = []

    def fake_run_command(
        args: Sequence[str | PathLike[str]],
        *,
        options: CommandOptions | None = None,
    ) -> CommandResult:
        """Capture the command contract and materialize a deterministic GIF output.

        Args:
            args: Executable and its explicit command-line arguments.
            options: Shared runner settings passed by the GIF builder.

        Returns:
            A successful command result with inherited output streams.
        """
        command = tuple(str(argument) for argument in args)
        calls.append((command, options))
        Path(command[-1]).write_bytes(b"GIF89a")
        return CommandResult(command, 0, None, None)

    monkeypatch.setattr(build_visual_gifs, "run_command", fake_run_command)

    build_visual_gifs.build("magick", [frame], output, "8", timeout=17)

    assert output.read_bytes() == b"GIF89a"
    assert len(calls) == 1
    command, options = calls[0]
    assert command[0:3] == ("magick", "-delay", "8")
    assert command[-1] == str(output)
    assert options == CommandOptions(check=True, timeout=17)
