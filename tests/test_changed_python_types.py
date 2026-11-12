"""Tests for changed-file annotation and generic-object debt ratchets."""

from __future__ import annotations

from tools.ci.check_changed_python_types import (
    annotation_regressions,
    object_annotation_regression,
)


def test_annotation_regressions_detect_per_rule_increases() -> None:
    """Report only Ruff annotation rules whose counts increased relative to the base."""
    current = {"ANN001": 3, "ANN201": 2, "ANN401": 0}
    baseline = {"ANN001": 2, "ANN201": 2, "ANN401": 1}

    assert annotation_regressions(current, baseline) == (("ANN001", 2, 3),)


def test_annotation_regressions_accepts_unchanged_or_reduced_debt() -> None:
    """Allow unchanged counts and reductions in historical missing-annotation debt."""
    current = {"ANN001": 1, "ANN201": 2}
    baseline = {"ANN001": 2, "ANN201": 2}

    assert annotation_regressions(current, baseline) == ()


def test_new_python_file_must_start_without_annotation_debt() -> None:
    """Treat a missing base file as zero existing annotation violations."""
    current = {"ANN001": 1, "ANN201": 1}

    assert annotation_regressions(current, {}) == (
        ("ANN001", 0, 1),
        ("ANN201", 0, 1),
    )


def test_object_annotation_regression_detects_increases() -> None:
    """Reject new generic object annotations while allowing the existing count."""
    assert object_annotation_regression(3, 2) == (2, 3)
    assert object_annotation_regression(2, 2) is None
    assert object_annotation_regression(1, 2) is None


def test_new_python_files_cannot_introduce_generic_object_annotations() -> None:
    """Treat a new module's allowed generic-object annotation count as zero."""
    assert object_annotation_regression(1, 0) == (0, 1)
    assert object_annotation_regression(0, 0) is None
