# Copyright (C) 2026 FreeCAD Cloth contributors
"""Shared opt-in diagnostic output for long-running simulation operations."""

from __future__ import annotations

import os
import sys


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
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as stream:
        stream.write(line)
        stream.flush()
