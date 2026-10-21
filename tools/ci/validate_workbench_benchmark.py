# Copyright (C) 2026 FreeCAD Cloth contributors
"""Validate isolated workbench startup and initialization benchmark artifacts."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import cast

WORKBENCH_NAMES = ("Pattern", "Sewing", "Simulation")


def _integer(value: object) -> int | None:
    """Return an integer metric while rejecting booleans and floats.

    Args:
        value: Candidate metric value to validate.

    Returns:
        Integer value, or None when the input is not an integer.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _number(value: object) -> float | None:
    """Return a finite numeric metric while rejecting booleans and malformed values.

    Args:
        value: Candidate metric value to validate.

    Returns:
        Finite numeric value, or None when the input is invalid.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def validate_metrics(payload: object, expected_workbench: str) -> list[str]:
    """Return schema, workbench identity, and measurement errors for one benchmark artifact.

    Args:
        payload: Decoded JSON value containing the benchmark artifact.
        expected_workbench: Workbench name associated with this matrix result.

    Returns:
        Human-readable errors for any invalid metadata or measurements.
    """
    if expected_workbench not in WORKBENCH_NAMES:
        return [f"unknown workbench: {expected_workbench!r}"]
    if not isinstance(payload, dict):
        return ["benchmark artifact must contain a JSON object"]

    metrics = cast("dict[str, object]", payload)
    errors: list[str] = []
    if _integer(metrics.get("schema")) != 2:
        errors.append("schema must be 2")

    python_version = metrics.get("python")
    if not isinstance(python_version, str) or not python_version:
        errors.append("python must be a non-empty string")

    freecad_version = metrics.get("freecad_version")
    if (
        not isinstance(freecad_version, list)
        or not freecad_version
        or any(not isinstance(part, str) or not part for part in freecad_version)
    ):
        errors.append("freecad_version must be a non-empty list of strings")

    repeats = _integer(metrics.get("repeats"))
    if repeats is None or repeats < 3:
        errors.append("repeats must be an integer >= 3")

    workbenches_value = metrics.get("workbenches")
    if not isinstance(workbenches_value, dict):
        errors.append("workbenches must be a JSON object")
        return errors

    workbenches = cast("dict[str, object]", workbenches_value)
    if set(workbenches) != {expected_workbench}:
        errors.append(f"workbenches must contain only {expected_workbench!r}")

    benchmark_value = workbenches.get(expected_workbench)
    if not isinstance(benchmark_value, dict):
        errors.append(f"workbenches.{expected_workbench} must be a JSON object")
        return errors

    benchmark = cast("dict[str, object]", benchmark_value)
    integer_fields = {
        "python_files": 1,
        "nonblank_loc": 1,
        "related_test_files": 0,
        "cloth_command_tokens": 0,
    }
    for key, minimum in integer_fields.items():
        value = _integer(benchmark.get(key))
        if value is None or value < minimum:
            errors.append(f"{key} must be an integer >= {minimum}")

    related_tests = benchmark.get("related_tests")
    if not isinstance(related_tests, list) or any(
        not isinstance(name, str) or not name for name in related_tests
    ):
        errors.append("related_tests must be a list of non-empty strings")
    else:
        related_test_files = _integer(benchmark.get("related_test_files"))
        if related_test_files is not None and len(related_tests) != related_test_files:
            errors.append("related_test_files must equal the length of related_tests")
        if len(set(related_tests)) != len(related_tests):
            errors.append("related_tests must contain unique names")

    for key in ("class_lookup_ms", "construct_ms", "initialize_ms"):
        value = _number(benchmark.get(key))
        if value is None or value < 0.0:
            errors.append(f"{key} must be a finite non-negative number")

    registered_commands = _number(benchmark.get("registered_commands"))
    if registered_commands is None or registered_commands < 0.0:
        errors.append("registered_commands must be a finite non-negative number")

    samples = _integer(benchmark.get("initialize_samples"))
    if samples is None:
        errors.append("initialize_samples must be an integer")
    elif repeats is not None and samples != repeats:
        errors.append("initialize_samples must equal repeats")

    return errors


def main() -> int:
    """Load and validate the metrics for one workbench-matrix entry.

    Returns:
        Process status indicating whether the benchmark artifact is valid.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metrics", type=Path, help="path to benchmark.json")
    parser.add_argument("workbench", choices=WORKBENCH_NAMES)
    args = parser.parse_args()

    try:
        payload = json.loads(args.metrics.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"workbench-benchmark=failed reason=unreadable-metrics error={exc}")
        return 1

    errors = validate_metrics(payload, args.workbench)
    if errors:
        for error in errors:
            print(f"workbench-benchmark=failed reason={error}")
        return 1

    metrics = cast("dict[str, object]", payload)
    workbench_value = cast("dict[str, object]", metrics["workbenches"])
    benchmark = cast("dict[str, object]", workbench_value[args.workbench])
    print(
        "workbench-benchmark=passed "
        f"workbench={args.workbench} repeats={metrics['repeats']} "
        f"initialize_ms={float(benchmark['initialize_ms']):.3f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
