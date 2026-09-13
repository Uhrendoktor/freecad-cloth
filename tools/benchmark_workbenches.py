#!/usr/bin/env python3
"""Measure the three public Cloth workbench boundaries.

Runtime measurements are collected inside the canonical FreeCAD CI image;
static counts make the result explainable and reproducible from the checkout.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import pathlib
import statistics
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
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


def source_lines(path: pathlib.Path) -> int:
    try:
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    except (UnicodeDecodeError, OSError):
        return 0


def static_metrics(name: str) -> dict:
    directory = PACKAGE_DIRS[name]
    py_files = sorted(directory.glob("*.py"))
    tests = [p.name for p in (ROOT / "tests").glob("test_*.py") if any(h in p.stem.lower() for h in TEST_HINTS[name])]
    return {
        "python_files": len(py_files),
        "nonblank_loc": sum(source_lines(p) for p in py_files),
        "related_test_files": len(set(tests)),
        "related_tests": sorted(set(tests)),
        "cloth_command_tokens": sum(p.read_text(encoding="utf-8").count('"Cloth') for p in py_files),
    }


def median_ms(samples: list[float]) -> float:
    return round(statistics.median(samples) * 1000.0, 3)


def runtime_metrics(name: str, repeats: int) -> dict:
    module_name, class_name = WORKBENCHES[name]
    print(f"benchmark: {name}: importing and constructing", flush=True)
    module = importlib.import_module(module_name)
    lookup_samples = []
    construct_samples = []
    wb_cls = getattr(module, class_name)
    for _ in range(repeats):
        t0 = time.perf_counter()
        getattr(module, class_name)
        lookup_samples.append(time.perf_counter() - t0)
        t0 = time.perf_counter()
        wb_cls()
        construct_samples.append(time.perf_counter() - t0)
    print(f"benchmark: {name}: initializing", flush=True)
    wb = wb_cls()
    t0 = time.perf_counter()
    wb.Initialize()
    initialize_ms = median_ms([time.perf_counter() - t0])
    print(f"benchmark: {name}: initialized ({initialize_ms} ms)", flush=True)
    return {
        "class_lookup_ms": median_ms(lookup_samples),
        "construct_ms": median_ms(construct_samples),
        "initialize_ms": initialize_ms,
        "initialize_samples": 1,
        "registered_commands": len(getattr(wb, "commands", ())),
    }


def close_gui():
    try:
        import FreeCADGui as Gui
        from PySide import QtWidgets
    except ImportError:
        try:
            import FreeCADGui as Gui
            from PySide2 import QtWidgets
        except ImportError:
            return
    window = Gui.getMainWindow()
    if window is not None:
        window.close()
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.quit()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="artifacts/workbench-benchmark/benchmark.json")
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--workbench", choices=tuple(WORKBENCHES), help="Measure only this workbench")
    args = parser.parse_args()
    if args.repeats < 3:
        raise SystemExit("--repeats must be >= 3")

    import FreeCAD

    names = [args.workbench] if args.workbench else list(WORKBENCHES)
    result = {
        "schema": 2,
        "python": __import__("sys").version.split()[0],
        "freecad_version": getattr(FreeCAD, "Version", lambda: ())(),
        "repeats": args.repeats,
        "workbenches": {},
    }
    for name in names:
        result["workbenches"][name] = {**static_metrics(name), **runtime_metrics(name, args.repeats)}

    out = ROOT / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True), flush=True)
    close_gui()
    os._exit(0)


if __name__ == "__main__":
    main()
