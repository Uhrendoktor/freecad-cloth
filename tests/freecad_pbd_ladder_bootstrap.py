# Copyright (C) 2026 FreeCAD Cloth contributors
"""Bootstrap repository paths and trace files for standalone FreeCAD ladder scripts."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import TextIO


def initialize_ladder(
    script_file: str | Path, ladder_name: str
) -> tuple[Path, Path, Path, Path, TextIO]:
    """Prepare import paths and an append-only startup trace for a ladder script.

    Args:
        script_file: Path of the standalone avatar or cube diagnostic script.
        ladder_name: Stable artifact prefix, either "avatar" or "cube".

    Returns:
        Repository root, helper directory, output directory, log path, and open log handle.

    Raises:
        OSError: If the artifact directory or its startup trace cannot be created.

    Side effects:
        Adds the repository and support directories to sys.path and opens the trace in append mode.
    """
    script_path = Path(script_file).resolve()
    repository_root = script_path.parents[1]
    helper_directory = script_path.parent / "support"
    for directory in (repository_root, helper_directory):
        if str(directory) not in sys.path:
            sys.path.insert(0, str(directory))

    output_directory = Path(
        os.environ.get("CLOTH_DIAGNOSTIC_DIR", "artifacts/pbd-contact-diagnostics")
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    bootstrap_log = output_directory / f"{ladder_name}-ladder-bootstrap.log"
    trace_handle = bootstrap_log.open("a", encoding="utf-8", buffering=1)
    return repository_root, helper_directory, output_directory, bootstrap_log, trace_handle
