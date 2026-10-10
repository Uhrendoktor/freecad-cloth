"""Fail a pytest validation group if any explicitly requested module collects no items."""

from __future__ import annotations

import os
import sys
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


class RequestedModuleCollection:
    """Enforce non-empty collection after the same pytest run executes tests."""

    def __init__(self, expected_paths: Iterable[str | Path]) -> None:
        self.expected_paths = tuple(Path(path).resolve() for path in expected_paths)

    @pytest.hookimpl(trylast=True)
    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        """Mark the run failed if any requested module generated no test items."""
        missing = missing_requested_modules(
            self.expected_paths,
            (item.path for item in session.items),
        )
        if missing:
            sys.stderr.write(
                "pytest modules collected no test items: " + ", ".join(missing) + "\n"
            )
            session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_configure(config: pytest.Config) -> None:
    """Register the collection contract for the expected module list in CI."""
    raw_paths = os.environ.get("CLOTH_EXPECTED_TEST_MODULES", "")
    if not raw_paths:
        raise pytest.UsageError("CLOTH_EXPECTED_TEST_MODULES must be set by python_validation.py")
    expected_paths = tuple(path for path in raw_paths.split(os.pathsep) if path)
    if not expected_paths:
        raise pytest.UsageError("CLOTH_EXPECTED_TEST_MODULES must contain at least one path")
    config.pluginmanager.register(
        RequestedModuleCollection(expected_paths),
        "requested-module-collection-contract",
    )
