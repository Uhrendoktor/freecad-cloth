"""Tests for the repository-wide explicit-Any and type-check workflow policies."""

from __future__ import annotations

import pytest

from tools.ci.check_explicit_any_annotations import explicit_any_violations
from tools.ci.validate_ci_structure import (
    TYPECHECK_COMMANDS,
    WORKFLOW,
    missing_typecheck_commands,
)


@pytest.mark.parametrize(
    "source",
    (
        "from typing import Any\nvalue: Any\n",
        "import typing\nvalue: dict[str, typing.Any]\n",
        "import typing as t\nvalue: list[t.Any]\n",
        "from typing import Any as Dynamic\nclass Model:\n    payload: Dynamic\n",
        "from typing_extensions import Any as Dynamic\nvalue = list[Dynamic]\n",
        "from typing import *\nvalue: Any\n",
        "from typing import Any\nAlias = dict[str, Any]\n",
    ),
)
def test_explicit_any_references_are_rejected(source: str) -> None:
    """Reject direct, renamed, qualified, wildcard, and type-alias Any usage."""
    assert explicit_any_violations(source)


def test_concrete_types_and_protocols_are_accepted() -> None:
    """Allow structural typing and object boundaries when they avoid Any."""
    source = """
from typing import Protocol, TypeAlias

JsonValue: TypeAlias = str | int | float | bool | None | list[object] | dict[str, object]

class Point(Protocol):
    x: float
    y: float

def consume(value: object) -> bool:
    return hasattr(value, "x") and hasattr(value, "y")
"""
    assert explicit_any_violations(source) == ()


def test_parse_errors_fail_closed() -> None:
    """Do not silently skip source when the AST parser cannot read it."""
    result = explicit_any_violations("value: Any =\n", "broken.py")
    assert result and result[0].startswith("broken.py:1: invalid Python syntax")


def test_canonical_workflow_contains_all_blocking_type_gates() -> None:
    """Require the AST gate plus broad and strict Pyright profiles in CI."""
    workflow_text = WORKFLOW.read_text(encoding="utf-8")
    assert missing_typecheck_commands(workflow_text) == ()


@pytest.mark.parametrize("command", TYPECHECK_COMMANDS)
def test_type_gate_contract_detects_removed_command(command: str) -> None:
    """Catch a workflow regression if any blocking type gate is removed."""
    workflow_text = WORKFLOW.read_text(encoding="utf-8")
    tampered = workflow_text.replace(command, "", 1)
    assert missing_typecheck_commands(tampered) == (command,)
