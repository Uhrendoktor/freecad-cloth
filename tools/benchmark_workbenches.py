#!/usr/bin/env python3
"""Measure the three public Cloth workbench boundaries.

The benchmark deliberately mixes runtime measurements with repository-derived
counts. Runtime numbers are collected inside the canonical FreeCAD CI image;
static counts make the result explainable and reproducible from the checkout.
"""
from __future__ import annotations

import argparse
import importlib
import json
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
    loc = sum(source_lines(p) for p in py_files)
    tests = []
    for p in (ROOT / "tests").glob("test_*.py"):
        stem = p.stem.lower()
        if any(hint in stem for hint in TEST_HINTS[name]):
            tests.append(p.name)
    command_tokens = 0
    for p in py_files:
        text = p.read_text(encoding="utf-8")
        command_tokens += text.count('"Cloth')
    return {
        "python_files": len(py_files),
        "nonblank_loc": loc,
        "related_test_files": len(set(tests)),
        "related_tests": sorted(set(tests)),
        "cloth_command_tokens": command_tokens,
    }


def median_ms(samples: list[float]) -> float:
    return round(statistics.median(samples) * 1000.0, 3)


def runtime_metrics(name: str, repeats: int) -> dict:
    module_name, class_name = WORKBENCHES[name]
    import_times = []
    construct_times = []
    init_times = []
    command_counts = []
    for _ in range(repeats):
        module = importlib.import_module(module_name)
        t0 = time.perf_counter()
        wb_cls = getattr(module, class_name)
        import_times.append(time.perf_counter() - t0)
        t0 = time.perf_counter()
        wb = wb_cls()
        construct_times.append(time.perf_counter() - t0)
        t0 = time.perf_counter()
        wb.Initialize()
        init_times.append(time.perf_counter() - t0)
        command_counts.append(len(getattr(wb, "commands", ())))
    return {
        "class_lookup_ms": median_ms(import_times),
        "construct_ms": median_ms(construct_times),
        "initialize_ms": median_ms(init_times),
        "registered_commands": max(command_counts),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="artifacts/workbench-benchmark/benchmark.json")
    parser.add_argument("--repeats", type=int, default=7)
    args = parser.parse_args()
    if args.repeats < 3:
        raise SystemExit("--repeats must be >= 3")

    # Import FreeCAD explicitly so the benchmark cannot silently run outside the
    # intended FreeCAD environment.
    import FreeCAD  # noqa: F401

    result = {
        "schema": 1,
        "python": __import__("sys").version.split()[0],
        "freecad_version": getattr(FreeCAD, "Version", lambda: ())(),
        "repeats": args.repeats,
        "workbenches": {},
    }
    for name in WORKBENCHES:
        result["workbenches"][name] = {
            **static_metrics(name),
            **runtime_metrics(name, args.repeats),
        }

    out = ROOT / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
