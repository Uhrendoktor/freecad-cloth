"""Validate that canonical pytest groups route and collect every requested test module."""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _normalize(paths: Iterable[str]) -> tuple[Path, ...]:
    """Return unique repository-relative test paths in stable order."""
    return tuple(dict.fromkeys((ROOT / path).resolve() for path in paths))


class _CollectionRecorder:
    """Record which test files produced collected pytest items."""

    def __init__(self) -> None:
        self.counts: Counter[Path] = Counter()

    def pytest_collection_modifyitems(self, items: list[pytest.Item]) -> None:
        for item in items:
            self.counts[Path(item.path).resolve()] += 1


def assert_collected(paths: Iterable[str]) -> None:
    """Fail closed when any requested test module collects zero pytest items."""
    expected = _normalize(paths)
    recorder = _CollectionRecorder()
    status = pytest.main(
        ["--collect-only", "-q", "--disable-warnings", *[str(path) for path in expected]],
        plugins=[recorder],
    )
    if status != pytest.ExitCode.OK:
        raise SystemExit(f"pytest collection failed with exit code {int(status)}")

    missing = [path.relative_to(ROOT).as_posix() for path in expected if not recorder.counts[path]]
    if missing:
        raise SystemExit("pytest modules collected no test items: " + ", ".join(missing))


def main() -> int:
    """Check one canonical validation group."""
    parser = argparse.ArgumentParser()
    parser.add_argument("tests", nargs="+")
    args = parser.parse_args()
    assert_collected(args.tests)
    print(f"pytest-collection=passed modules={len(args.tests)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
