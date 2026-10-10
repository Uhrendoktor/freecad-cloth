"""Fail a pytest validation group if any explicitly requested module collects no items."""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

import pytest


def missing_requested_modules(
    expected_paths: Iterable[str | Path],
    collected_paths: Iterable[str | Path],
) -> tuple[str, ...]:
    """Return requested paths absent from the collected test-item paths."""
    root = Path.cwd().resolve()
    expected = tuple(dict.fromkeys(Path(path).resolve() for path in expected_paths))
    collected = {Path(path).resolve() for path in collected_paths}
    return tuple(
        path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path)
        for path in expected
        if path not in collected
    )


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Fail this same pytest run if an explicitly requested module collects no tests."""
    raw_paths = os.environ.get("CLOTH_EXPECTED_TEST_MODULES", "")
    if not raw_paths:
        raise pytest.UsageError("CLOTH_EXPECTED_TEST_MODULES must be set by python_validation.py")
    expected_paths: list[str] = []
    for line in raw_paths.splitlines():
        expected_paths.extend(path for path in line.split(os.pathsep) if path)
    if not expected_paths:
        raise pytest.UsageError("CLOTH_EXPECTED_TEST_MODULES must contain at least one path")
    missing = missing_requested_modules(expected_paths, (item.path for item in items))
    if missing:
        raise pytest.UsageError("pytest modules collected no test items: " + ", ".join(missing))
