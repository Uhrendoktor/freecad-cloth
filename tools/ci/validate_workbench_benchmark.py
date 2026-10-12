"""Validate the workbench benchmark artifact produced by FreeCAD CI."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import cast

TIMING_KEYS = ("class_lookup_ms", "construct_ms", "initialize_ms")
COUNT_KEYS = (
    "python_files",
    "nonblank_loc",
    "related_test_files",
    "cloth_command_tokens",
    "initialize_samples",
)


def _number(value: object) -> float | None:
    """Return a finite numeric metric, rejecting booleans and malformed values."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _integer(value: object) -> int | None:
    """Return an integer metric without accepting booleans or truncated floats."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def validate_payload(payload: object, expected_workbench: str) -> list[str]:
    """Return all schema and metric failures for one workbench benchmark artifact."""
    if not isinstance(payload, dict):
        return ["benchmark artifact must contain a JSON object"]
    record = cast(dict[str, object], payload)
    errors: list[str] = []

    if _integer(record.get("schema")) != 2:
        errors.append("schema must be 2")
    python_version = record.get("python")
    if not isinstance(python_version, str) or not python_version:
        errors.append("python must be a non-empty string")
    freecad_version = record.get("freecad_version")
    if isinstance(freecad_version, str):
        if not freecad_version:
            errors.append("freecad_version must not be empty")
    elif (
        not isinstance(freecad_version, (list, tuple))
        or not freecad_version
        or any(not isinstance(part, str) or not part for part in freecad_version)
    ):
        errors.append("freecad_version must be a non-empty string or string sequence")

    repeats = _integer(record.get("repeats"))
    if repeats is None or repeats < 3:
        errors.append("repeats must be an integer >= 3")

    workbench_value = record.get("workbenches")
    if not isinstance(workbench_value, dict):
        errors.append("workbenches must be a JSON object")
        return errors
    workbenches = cast(dict[str, object], workbench_value)
    if set(workbenches) != {expected_workbench}:
        errors.append(f"workbenches must contain only {expected_workbench}")
        return errors

    metric_value = workbenches.get(expected_workbench)
    if not isinstance(metric_value, dict):
        errors.append(f"workbenches.{expected_workbench} must be a JSON object")
        return errors
    metrics = cast(dict[str, object], metric_value)

    for key in COUNT_KEYS:
        value = _integer(metrics.get(key))
        if value is None or value < 0:
            errors.append(f"{key} must be a non-negative integer")
    related_tests = metrics.get("related_tests")
    if not isinstance(related_tests, list) or any(
        not isinstance(name, str) or not name for name in related_tests
    ):
        errors.append("related_tests must be a list of non-empty strings")
    elif _integer(metrics.get("related_test_files")) != len(related_tests):
        errors.append("related_test_files must equal the number of related_tests")
    for key in TIMING_KEYS:
        value = _number(metrics.get(key))
        if value is None or value < 0.0:
            errors.append(f"{key} must be a finite non-negative number")
    commands = _number(metrics.get("registered_commands"))
    if commands is None or commands < 0.0:
        errors.append("registered_commands must be a finite non-negative number")
    if repeats is not None and _integer(metrics.get("initialize_samples")) != repeats:
        errors.append("initialize_samples must equal repeats")

    return errors


def main() -> int:
    """Read and validate a saved workbench benchmark artifact."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metrics", type=Path, help="path to benchmark JSON")
    parser.add_argument("--workbench", required=True, choices=("Pattern", "Sewing", "Simulation"))
    args = parser.parse_args()
    try:
        payload = json.loads(args.metrics.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"workbench-benchmark=failed reason=cannot read artifact: {exc}")
        return 1
    errors = validate_payload(payload, args.workbench)
    for error in errors:
        print(f"workbench-benchmark=failed reason={error}")
    if errors:
        return 1
    print(f"workbench-benchmark=passed workbench={args.workbench}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
