"""Independently validate workbench benchmark artifacts produced by FreeCAD CI."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import cast

WORKBENCH_NAMES = ("Pattern", "Sewing", "Simulation")
TIMING_FIELDS = ("class_lookup_ms", "construct_ms", "initialize_ms")


def _integer(value: object) -> int | None:
    """Return an integer without accepting booleans or truncated floats."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _number(value: object) -> float | None:
    """Return a finite real number; reject booleans and malformed metrics."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _valid_version(value: object) -> bool:
    """Accept the string or component-list forms emitted by FreeCAD.Version()."""
    if isinstance(value, str):
        return bool(value.strip())
    if not isinstance(value, list) or not value:
        return False
    return all(
        (isinstance(part, str) and bool(part.strip()))
        or (isinstance(part, int) and not isinstance(part, bool))
        for part in value
    )


def validate_payload(payload: object, expected_workbench: str | None = None) -> list[str]:
    """Return all structural and consistency failures in a workbench benchmark."""
    if not isinstance(payload, dict):
        return ["benchmark artifact must contain a JSON object"]

    data = cast(dict[str, object], payload)
    errors: list[str] = []
    if _integer(data.get("schema")) != 2:
        errors.append("schema must be 2")
    if not isinstance(data.get("python"), str) or not str(data["python"]).strip():
        errors.append("python must be a non-empty string")
    if not _valid_version(data.get("freecad_version")):
        errors.append("freecad_version must be a non-empty version string or component list")

    repeats = _integer(data.get("repeats"))
    if repeats is None or repeats < 3:
        errors.append("repeats must be an integer >= 3")

    if expected_workbench is not None and expected_workbench not in WORKBENCH_NAMES:
        errors.append("expected_workbench must be Pattern, Sewing, or Simulation")

    raw_workbenches = data.get("workbenches")
    if not isinstance(raw_workbenches, dict):
        errors.append("workbenches must be a JSON object")
        return errors

    workbenches = cast(dict[str, object], raw_workbenches)
    if len(workbenches) != 1:
        errors.append("workbenches must contain exactly one entry")
    if expected_workbench is not None and set(workbenches) != {expected_workbench}:
        errors.append(f"workbenches must contain only the expected {expected_workbench!r} entry")

    for name, raw_metrics in workbenches.items():
        if name not in WORKBENCH_NAMES:
            errors.append(f"unsupported workbench name: {name!r}")
        if not isinstance(raw_metrics, dict):
            errors.append(f"workbenches.{name} must be a JSON object")
            continue
        metrics = cast(dict[str, object], raw_metrics)

        for key, minimum in (
            ("python_files", 1),
            ("nonblank_loc", 1),
            ("related_test_files", 1),
            ("cloth_command_tokens", 0),
        ):
            count = _integer(metrics.get(key))
            if count is None or count < minimum:
                errors.append(f"workbenches.{name}.{key} must be an integer >= {minimum}")

        related_tests = metrics.get("related_tests")
        related_count = _integer(metrics.get("related_test_files"))
        if (
            not isinstance(related_tests, list)
            or not related_tests
            or any(not isinstance(item, str) or not item.strip() for item in related_tests)
        ):
            errors.append(f"workbenches.{name}.related_tests must be a non-empty string list")
        else:
            if len(set(related_tests)) != len(related_tests):
                errors.append(f"workbenches.{name}.related_tests must not contain duplicates")
            if related_count is not None and related_count != len(related_tests):
                errors.append(
                    f"workbenches.{name}.related_test_files must equal the number of related_tests"
                )

        for key in TIMING_FIELDS:
            value = _number(metrics.get(key))
            if value is None or value < 0.0:
                errors.append(f"workbenches.{name}.{key} must be a finite non-negative number")

        samples = _integer(metrics.get("initialize_samples"))
        if samples is None or samples < 3:
            errors.append(f"workbenches.{name}.initialize_samples must be an integer >= 3")
        elif repeats is not None and samples != repeats:
            errors.append(f"workbenches.{name}.initialize_samples must equal repeats")

        commands = _number(metrics.get("registered_commands"))
        if commands is None or commands < 1.0:
            errors.append(f"workbenches.{name}.registered_commands must be >= 1")

    return errors


def main() -> int:
    """Read and independently validate a saved workbench benchmark artifact."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metrics", type=Path, help="path to benchmark.json produced by FreeCAD")
    parser.add_argument("--workbench", choices=WORKBENCH_NAMES)
    args = parser.parse_args()

    try:
        payload = json.loads(args.metrics.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(
            f"workbench-benchmark=failed reason=unreadable-artifact error={exc}"
        ) from exc

    errors = validate_payload(payload, expected_workbench=args.workbench)
    if errors:
        for error in errors:
            print(f"workbench-benchmark=failed reason={error}", flush=True)
        return 1

    data = cast(dict[str, object], payload)
    workbenches = cast(dict[str, object], data["workbenches"])
    name = args.workbench or next(iter(workbenches))
    repeats = _integer(data.get("repeats"))
    if repeats is None:
        return 1
    print(f"workbench-benchmark=passed workbench={name} repeats={repeats}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
