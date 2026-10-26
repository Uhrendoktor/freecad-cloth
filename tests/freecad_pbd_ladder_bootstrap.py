# Copyright (C) 2026 FreeCAD Cloth contributors
"""Bootstrap repository paths and trace files for standalone FreeCAD ladder scripts."""

from __future__ import annotations

import faulthandler
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType
    from typing import TextIO


class LadderBootstrap(NamedTuple):
    """Runtime dependencies consumed by a standalone PBD ladder."""

    output_directory: Path
    boot: Callable[[str], None]
    app: ModuleType
    gui: ModuleType
    part: ModuleType


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
) -> LadderBootstrap:
    """Initialize trace logging and import the FreeCAD runtime through one path.

    Args:
        script_file: File path of the standalone avatar or cube ladder.
        ladder_name: Stable artifact prefix, either "avatar" or "cube".

    Returns:
        A typed bundle with the output directory, trace callback, and imported
        FreeCAD application, GUI, and Part modules.

    Raises:
        ImportError: If FreeCAD or its GUI/Part modules cannot be imported.
        OSError: If the artifact directory or startup trace cannot be created.
    """
    repository_root, helper_directory, output_directory, log_path, trace = initialize_ladder(
        script_file, ladder_name
    )

    def boot(message: str) -> None:
        """Write one startup checkpoint to the append-only trace."""
        trace.write(str(message) + "\n")
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
    return LadderBootstrap(output_directory, boot, App, Gui, Part)


def dispatch_ladder_entrypoint(
    script_file: str | Path,
    module_name: str,
    callback: Callable[[], None],
    boot: Callable[[str], None],
    app: ModuleType,
    schedule: Callable[[Callable[[], None]], None],
) -> None:
    """Run or schedule a FreeCAD ladder after the host has loaded its script.

    Args:
        script_file: Path of the standalone ladder script.
        module_name: Module name assigned by the Python or FreeCAD host.
        callback: Main ladder callback, including its shutdown handling.
        boot: Append-only trace callback for startup checkpoints.
        app: Imported FreeCAD application module.
        schedule: FreeCAD event-loop scheduling function.

    Side effects:
        Calls the ladder directly for normal Python execution, or schedules it
        for FreeCAD's delayed-startup callback.
    """
    boot(f"entrypoint-name={module_name!r}")
    boot("entrypoint-argv0=%r" % (sys.argv[0] if sys.argv else ""))
    entrypoint_name = Path(script_file).stem
    gui_hosted = bool(getattr(app, "GuiUp", False))
    if module_name == "__main__":
        boot("direct-entrypoint")
        callback()
    elif gui_hosted or module_name == entrypoint_name:
        boot("freecad-hosted-entrypoint")
        boot("entrypoint:schedule-main")
        schedule(callback)
