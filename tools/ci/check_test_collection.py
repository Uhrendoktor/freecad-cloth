"""Pytest plugin that verifies every requested validation module collects test items."""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _normalize(paths: Iterable[str]) -> tuple[Path, ...]:
    """Return unique repository-relative test paths in stable order."""
    return tuple(dict.fromkeys((ROOT / path).resolve() for path in paths))


def _missing_test_modules(paths: Iterable[str], collected_paths: Iterable[Path]) -> tuple[str, ...]:
    """Return requested modules that produced no collected test items."""
    expected = _normalize(paths)
    collected = {Path(path).resolve() for path in collected_paths}
    return tuple(path.relative_to(ROOT).as_posix() for path in expected if path not in collected)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Fail the in-session pytest run when a requested module collects no items."""
    configured = os.environ.get("CLOTH_EXPECTED_TEST_MODULES", "")
    if not configured.strip():
        return
    expected = tuple(line.strip() for line in configured.splitlines() if line.strip())
    missing = _missing_test_modules(expected, (Path(item.path) for item in items))
    if missing:
        raise pytest.UsageError("pytest modules collected no test items: " + ", ".join(missing))
