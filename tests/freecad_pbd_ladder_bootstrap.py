# Copyright (C) 2026 FreeCAD Cloth contributors
"""Bootstrap repository paths and trace files for standalone FreeCAD ladder scripts."""

from __future__ import annotations

import faulthandler
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType
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

def bootstrap_ladder(
    script_file: str | Path,
    ladder_name: str,
) -> tuple[
    Path,
    Path,
    Path,
    Path,
    TextIO,
    Callable[[str], None],
    ModuleType,
    ModuleType,
    ModuleType,
]:
    """Initialize trace logging and import the FreeCAD runtime through one path.

    Args:
        script_file: File path of the standalone avatar or cube ladder.
        ladder_name: Stable artifact prefix, either "avatar" or "cube".

    Returns:
        Repository root, helper directory, output directory, log path, trace
        handle, logging callback, FreeCAD application module, GUI module, and Part.

    Raises:
        ImportError: If FreeCAD or its GUI/Part modules cannot be imported.
        OSError: If the artifact directory or startup trace cannot be created.
    """
    repository_root, helper_directory, output_directory, log_path, trace = (
        initialize_ladder(script_file, ladder_name)
    )

    def boot(message: str) -> None:
        """Write one startup checkpoint to the append-only trace."""
        trace.write(str(message) + "\\n")
        trace.flush()

    boot("script-start")
    boot("before-import-FreeCAD")
    import FreeCAD as App

    boot("import-FreeCAD-complete")
    boot("before-import-FreeCADGui")
    import FreeCADGui as Gui

    boot("import-FreeCADGui-complete")
    boot("before-import-Part")
    import Part

    boot("import-Part-complete")
    try:
        faulthandler.enable(file=trace, all_threads=True)
        faulthandler.dump_traceback_later(30.0, repeat=True, file=trace)
        boot("diagnostic-faulthandler-ready")
    except (AttributeError, OSError, RuntimeError, ValueError) as exc:
        boot(f"diagnostic-faulthandler-unavailable={exc!r}")
    boot("before-support-helper-import")
    return (
        repository_root,
        helper_directory,
        output_directory,
        log_path,
        trace,
        boot,
        App,
        Gui,
        Part,
    )
\n