"""Tests for non-regression of missing-annotation debt on changed Python files."""

from __future__ import annotations

from tools.ci.check_changed_python_types import annotation_regressions


def test_annotation_regressions_detects_per_rule_increases() -> None:
    """Report only annotation rules whose counts increased relative to the base."""
    current = {"ANN001": 3, "ANN201": 2, "ANN401": 0}
    baseline = {"ANN001": 2, "ANN201": 2, "ANN401": 1}

    assert annotation_regressions(current, baseline) == (("ANN001", 2, 3),)


def test_annotation_regressions_accepts_unchanged_or_reduced_debt() -> None:
    """Allow unchanged counts and any reduction in the historical annotation backlog."""
    current = {"ANN001": 1, "ANN201": 2}
    baseline = {"ANN001": 2, "ANN201": 2}

    assert annotation_regressions(current, baseline) == ()


def test_new_python_file_must_start_without_annotation_debt() -> None:
    """A missing baseline is equivalent to zero existing violations."""
    current = {"ANN001": 1, "ANN201": 1}

    assert annotation_regressions(current, {}) == (
        ("ANN001", 0, 1),
        ("ANN201", 0, 1),
    )
