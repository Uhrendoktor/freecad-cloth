# Copyright (C) 2026 FreeCAD Cloth contributors
"""Measure the three public Cloth workbench boundaries."""

from __future__ import annotations

import argparse
import contextlib
import importlib
import json
import os
import pathlib
import statistics
import sys
import tempfile
import time
import traceback
from collections.abc import Callable, Sequence
from types import ModuleType
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from typing import NoReturn

ROOT = pathlib.Path(__file__).resolve().parents[1]
TRACE_LOG_PATH = pathlib.Path(tempfile.gettempdir()) / "cloth-benchmark-trace.log"
TRACEBACK_LOG_PATH = pathlib.Path(tempfile.gettempdir()) / "cloth-benchmark-traceback.log"
EXPECTED_REGISTERED_WORKBENCH_COUNT = 1
MINIMUM_BENCHMARK_REPEATS = 3
WORKBENCHES = {
    "Pattern": ("freecad_cloth.pattern.workbench", "ClothPatternWorkbench"),
    "Sewing": ("freecad_cloth.sewing.workbench", "ClothSewingWorkbench"),
    "Simulation": ("freecad_cloth.simulation.workbench", "ClothSimulationWorkbench"),
}
PACKAGE_DIRS = {
    "Pattern": ROOT / "freecad_cloth" / "pattern",
    "Sewing": ROOT / "freecad_cloth" / "sewing",
    "Simulation": ROOT / "freecad_cloth" / "simulation",
}
TEST_HINTS = {
    "Pattern": ("pattern", "sketch", "export", "topology", "marks"),
    "Sewing": ("sewing", "show2d", "network"),
    "Simulation": ("simulation", "drape", "quality", "avatar", "collision", "xpbd", "solver"),
}


class BenchmarkWorkbenchBackend:
    """No-op GUI backend used only to isolate Python Initialize() work."""

    @staticmethod
    def append_toolbar(name: str, commands: list[str]) -> None:
        """Accept toolbar registration without creating GUI state during timing runs.

        Args:
            name: Toolbar label supplied by the workbench.
            commands: Command identifiers that would normally populate the toolbar.
        """
        del name, commands

    @staticmethod
    def append_menu(name: str, commands: list[str]) -> None:
        """Accept menu registration without creating GUI state during timing runs.

        Args:
            name: Menu label supplied by the workbench.
            commands: Command identifiers that would normally populate the menu.
        """
        del name, commands

    @staticmethod
    def append_context_menu(name: str, commands: list[str]) -> None:
        """Accept context-menu registration without creating GUI state during timing runs.

        Args:
            name: Context-menu label supplied by the workbench.
            commands: Command identifiers that would normally populate the menu.
        """
        del name, commands


# Register FreeCAD's legacy callback names without defining non-PEP-8 methods.
setattr(
    BenchmarkWorkbenchBackend,
    "appendToolbar",
    staticmethod(BenchmarkWorkbenchBackend.append_toolbar),
)
setattr(
    BenchmarkWorkbenchBackend,
    "appendMenu",
    staticmethod(BenchmarkWorkbenchBackend.append_menu),
)
setattr(
    BenchmarkWorkbenchBackend,
    "appendContextMenu",
    staticmethod(BenchmarkWorkbenchBackend.append_context_menu),
)


def trace(message: str) -> None:
    """Write a benchmark diagnostic to the temporary trace file and console.

    Args:
        message: Diagnostic text describing the current benchmark stage.
    """
    with contextlib.suppress(OSError), TRACE_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(message + "\n")
    sys.stdout.write(message + "\n")
    sys.stdout.flush()


def fail(context: str, exc: BaseException) -> NoReturn:
    """Record a benchmark failure and stop the process with a non-zero status.

    Args:
        context: Stage or operation that failed.
        exc: Original exception whose traceback should be preserved.

    Raises:
        SystemExit: Always raised after recording the diagnostic and traceback.
    """
    detail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    trace(f"benchmark: FAILURE: {context}: {exc!r}")
    with contextlib.suppress(OSError):
        TRACEBACK_LOG_PATH.write_text(detail, encoding="utf-8")
    raise SystemExit(1)


def source_lines(path: pathlib.Path) -> int:
    """Count non-blank source lines, returning zero when the file cannot be read.

    Args:
        path: Python source file whose non-blank lines are counted.

    Returns:
        Number of non-blank lines, or zero for an unreadable or undecodable file.
    """
    try:
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    except (UnicodeDecodeError, OSError):
        return 0


def static_metrics(name: str) -> dict[str, object]:
    """Collect source-size, related-test, and command-token metrics for a workbench.

    Args:
        name: Workbench key present in the package-directory and test-hint inventories.

    Returns:
        Inventory metrics, non-blank source-line count, and related test filenames.
    """
    directory = PACKAGE_DIRS[name]
    py_files = sorted(directory.glob("*.py"))
    tests = [
        p.name
        for p in (ROOT / "tests").glob("test_*.py")
        if any(h in p.stem.lower() for h in TEST_HINTS[name])
    ]
    return {
        "python_files": len(py_files),
        "nonblank_loc": sum(source_lines(p) for p in py_files),
        "related_test_files": len(set(tests)),
        "related_tests": sorted(set(tests)),
        "cloth_command_tokens": sum(
            p.read_text(encoding="utf-8").count('"Cloth') for p in py_files
        ),
    }


def median_ms(samples: list[float]) -> float:
    """Convert the median duration from seconds to rounded milliseconds.

    Args:
        samples: Measured durations in seconds.

    Returns:
        Median duration in milliseconds, rounded to three decimal places.
    """
    return round(statistics.median(samples) * 1000.0, 3)


def _initialize_sample(
    gui_module: ModuleType,
    workbench_class: Callable[[], object],
    sample_number: int,
    sample_count: int,
) -> tuple[float, int]:
    """Initialize one workbench sample and return its duration and command count.

    Args:
        gui_module: Lazily loaded FreeCAD GUI module.
        workbench_class: Workbench constructor selected by the benchmark inventory.
        sample_number: One-based sample index used in progress diagnostics.
        sample_count: Total samples requested for this workbench.

    Returns:
        Elapsed initialization time in seconds and the number of registered commands.

    Raises:
        RuntimeError: If the GUI registers zero or multiple workbenches for one instance.
    """
    list_workbenches = cast(Callable[[], list[str]], getattr(gui_module, "listWorkbenches"))
    add_workbench = cast(Callable[[object], None], getattr(gui_module, "addWorkbench"))
    remove_workbench = cast(Callable[[str], None], getattr(gui_module, "removeWorkbench"))
    workbench = workbench_class()
    existing = set(list_workbenches())
    started_at = time.perf_counter()
    add_workbench(workbench)
    added = set(list_workbenches()) - existing
    if len(added) != EXPECTED_REGISTERED_WORKBENCH_COUNT:
        msg = f"expected one registered workbench, got {sorted(added)!r}"
        raise RuntimeError(msg)
    registered_name = next(iter(added))
    namespace = cast(dict[str, object], getattr(workbench, "__dict__"))
    namespace["__Workbench__"] = BenchmarkWorkbenchBackend()
    initialize = cast(Callable[[], None], getattr(workbench, "Initialize"))
    initialize()
    elapsed_seconds = time.perf_counter() - started_at
    commands = cast(Sequence[object], getattr(workbench, "commands", ()))
    with contextlib.suppress(Exception):
        remove_workbench(registered_name)
    trace(
        f"benchmark: {registered_name}: initialize sample "
        f"{sample_number}/{sample_count}"
    )
    return elapsed_seconds, len(commands)


def runtime_metrics(name: str, repeats: int) -> dict[str, object]:
    """Measure import, construction, and GUI initialization time for a workbench.

    Args:
        name: Workbench key used to resolve its implementation module and class.
        repeats: Number of independent lookup, construction, and initialization samples.

    Returns:
        Median timings, completed sample count, and the median registered-command count.

    Raises:
        RuntimeError: If FreeCAD registers an unexpected number of workbenches.
    """
    module_name, class_name = WORKBENCHES[name]
    trace(f"benchmark: {name}: importing and constructing")
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        fail(f"{name} import", exc)
    trace(f"benchmark: {name}: module imported")
    lookup_samples: list[float] = []
    construct_samples: list[float] = []
    workbench_class = cast(Callable[[], object], getattr(module, class_name))
    for _ in range(repeats):
        started_at = time.perf_counter()
        getattr(module, class_name)
        lookup_samples.append(time.perf_counter() - started_at)
        started_at = time.perf_counter()
        try:
            workbench_class()
        except Exception as exc:
            fail(f"{name} construction", exc)
        construct_samples.append(time.perf_counter() - started_at)

    trace(f"benchmark: {name}: initializing ({repeats} samples)")
    initialize_samples: list[float] = []
    command_counts: list[int] = []
    try:
        gui_module = importlib.import_module("FreeCADGui")
        for sample_number in range(1, repeats + 1):
            elapsed_seconds, command_count = _initialize_sample(
                gui_module,
                workbench_class,
                sample_number,
                repeats,
            )
            initialize_samples.append(elapsed_seconds)
            command_counts.append(command_count)
    except Exception as exc:
        fail(f"{name} initialization", exc)

    return {
        "class_lookup_ms": median_ms(lookup_samples),
        "construct_ms": median_ms(construct_samples),
        "initialize_ms": median_ms(initialize_samples),
        "initialize_samples": len(initialize_samples),
        "registered_commands": statistics.median(command_counts),
    }


def close_gui() -> None:
    """Close the FreeCAD main window and quit its Qt application when available."""
    try:
        gui_module = importlib.import_module("FreeCADGui")
    except ImportError:
        return
    try:
        widget_module = importlib.import_module("PySide")
    except ImportError:
        try:
            widget_module = importlib.import_module("PySide2")
        except ImportError:
            return
    window = getattr(gui_module, "getMainWindow")()
    if window is not None:
        window.close()
    qt_widgets = getattr(widget_module, "QtWidgets")
    application = getattr(qt_widgets, "QApplication").instance()
    if application is not None:
        application.quit()


def main() -> None:
    """Run the selected workbench measurements and write a JSON benchmark artifact.

    Raises:
        SystemExit: If the repeat count is invalid or a required FreeCAD step fails.
    """
    trace("benchmark: script entered")
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="artifacts/workbench-benchmark/benchmark.json")
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument(
        "--workbench", choices=tuple(WORKBENCHES), help="Measure only this workbench"
    )
    if os.environ.get("CLOTH_BENCHMARK_WORKBENCH"):
        args = parser.parse_args(
            [
                "--workbench",
                os.environ["CLOTH_BENCHMARK_WORKBENCH"],
                "--output",
                os.environ.get(
                    "CLOTH_BENCHMARK_OUTPUT", "artifacts/workbench-benchmark/benchmark.json"
                ),
                "--repeats",
                os.environ.get("CLOTH_BENCHMARK_REPEATS", "7"),
            ]
        )
    else:
        args = parser.parse_args()
    if args.repeats < MINIMUM_BENCHMARK_REPEATS:
        msg = f"--repeats must be >= {MINIMUM_BENCHMARK_REPEATS}"
        raise SystemExit(msg)
    trace("benchmark: arguments parsed")

    trace("benchmark: FreeCAD import starting")
    try:
        freecad_module = importlib.import_module("FreeCAD")
    except Exception as exc:
        fail("FreeCAD import", exc)
    trace("benchmark: FreeCAD import complete")

    names = [args.workbench] if args.workbench else list(WORKBENCHES)
    result = {
        "schema": 2,
        "python": sys.version.split()[0],
        "freecad_version": getattr(freecad_module, "Version", lambda: ())(),
        "repeats": args.repeats,
        "workbenches": {},
    }
    for name in names:
        result["workbenches"][name] = {
            **static_metrics(name),
            **runtime_metrics(name, args.repeats),
        }

    out = ROOT / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    trace("benchmark: JSON written")
    sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    sys.stdout.flush()
    close_gui()
    os._exit(0)


if __name__ == "__main__":
    # FreeCAD loads Python files through its delayed-startup event. Defer the
    # benchmark one event-loop turn so addWorkbench is not called re-entrantly
    # from the file-import machinery (which can crash FreeCAD/Qt).
    try:
        from PySide import QtCore
    except ImportError:
        from PySide2 import QtCore
    QtCore.QTimer.singleShot(0, main)
