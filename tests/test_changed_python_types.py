# Copyright (C) 2026 FreeCAD Cloth contributors
"""Tests for non-regression of missing-annotation debt on changed Python files."""

from __future__ import annotations

from tests.support.assertions import require
from tools.ci.check_changed_python_types import annotation_regressions


def test_annotation_regressions_detects_per_rule_increases() -> None:
    """Report only annotation rules whose counts increased relative to the base."""
    current = {"ANN001": 3, "ANN201": 2, "ANN401": 0}
    baseline = {"ANN001": 2, "ANN201": 2, "ANN401": 1}
    expected = (("ANN001", 2, 3),)

    require(
        condition=annotation_regressions(current, baseline) == expected,
        message="only the ANN001 increase should be reported",
    )


def test_annotation_regressions_accepts_unchanged_or_reduced_debt() -> None:
    """Allow unchanged counts and any reduction in the historical annotation backlog."""
    current = {"ANN001": 1, "ANN201": 2}
    baseline = {"ANN001": 2, "ANN201": 2}
    expected: tuple[tuple[str, int, int], ...] = ()

    require(
        condition=annotation_regressions(current, baseline) == expected,
        message="unchanged and reduced counts should produce no regression",
    )


def test_new_python_file_must_start_without_annotation_debt() -> None:
    """A missing baseline is equivalent to zero existing violations."""
    current = {"ANN001": 1, "ANN201": 1}
    expected = (("ANN001", 0, 1), ("ANN201", 0, 1))

    require(
        condition=annotation_regressions(current, {}) == expected,
        message="each new annotation violation should be reported against zero",
    )
