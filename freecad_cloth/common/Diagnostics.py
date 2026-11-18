# Copyright (C) 2026 FreeCAD Cloth contributors
"""Shared opt-in diagnostic output for long-running simulation operations."""

from __future__ import annotations

import os
import sys
from typing import TextIO

_DIAGNOSTIC_STREAM: TextIO | None = None
_DIAGNOSTIC_STREAM_PATH: str | None = None


def emit_diagnostic(message: str, *, enabled: bool = True) -> None:
    """Write a flushed diagnostic line to stdout and an optional profile file.

    Args:
        message: Structured diagnostic text without a trailing newline.
        enabled: Whether this diagnostic channel is currently enabled.
    """
    if not enabled:
        return
    line = f"{message}\n"
    sys.stdout.write(line)
    sys.stdout.flush()
    path = os.environ.get("CLOTH_INTER_CLOTH_DIAGNOSTICS_FILE")
    if path is None:
        return
    global _DIAGNOSTIC_STREAM, _DIAGNOSTIC_STREAM_PATH
    if path != _DIAGNOSTIC_STREAM_PATH:
        if _DIAGNOSTIC_STREAM is not None:
            _DIAGNOSTIC_STREAM.close()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        # Retain this process-lifetime stream to avoid reopening it for each sample.
        _DIAGNOSTIC_STREAM = open(path, "a", encoding="utf-8")  # noqa: SIM115
        _DIAGNOSTIC_STREAM_PATH = path
    if _DIAGNOSTIC_STREAM is not None:
        _DIAGNOSTIC_STREAM.write(line)
        _DIAGNOSTIC_STREAM.flush()
