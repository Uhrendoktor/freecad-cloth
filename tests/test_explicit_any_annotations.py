"""Tests for the repository-wide explicit-Any and type-check workflow policies."""

from __future__ import annotations

import json

import pytest

from tools.ci.check_explicit_any_annotations import explicit_any_violations
from tools.ci.validate_ci_structure import (
    PYRIGHT_CONFIG,
    TY_CONFIG,
    TYPECHECK_COMMANDS,
    WORKFLOW,
    missing_typecheck_commands,
    pyright_coverage_gaps,
    ty_warnings_are_blocking,
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


@pytest.mark.parametrize(
    "source",
    (
        "from typing import Any\ndef render(value: 'Any') -> 'list[Any]':\n    return [value]\n",
        "import typing as t\ndef render(value: 't.Any') -> None:\n    return None\n",
        "from typing import Any as Dynamic\ndef render(value: 'Dynamic') -> None:\n    return None\n",
        "from typing import Any\ndef render(value): # type: (Any) -> Any\n    return value\n",
        "from typing import Any\nvalue = 1 # type: Any\n",
    ),
)
def test_stringified_annotations_and_type_comments_are_rejected(source: str) -> None:
    """Inspect quoted forward references and legacy type comments as type syntax."""
    assert explicit_any_violations(source)


def test_ordinary_strings_are_not_parsed_as_type_syntax() -> None:
    """Leave ordinary text strings alone even when they contain the token Any."""
    source = "from typing import Any\nmessage = 'Any'\ncaption = 'typing.Any'\n"
    assert explicit_any_violations(source) == ()


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


def test_pyright_coverage_includes_every_production_module() -> None:
    """Require Pyright coverage to track the entire production tree."""
    config_text = PYRIGHT_CONFIG.read_text(encoding="utf-8")
    assert pyright_coverage_gaps(config_text) == ()


def test_pyright_coverage_guard_detects_a_narrowed_include_set() -> None:
    """Catch future edits that silently reduce the Pyright include set."""
    config = json.loads(PYRIGHT_CONFIG.read_text(encoding="utf-8"))
    config["include"] = ["freecad_cloth/simulation/ClothBackend.py"]
    gaps = pyright_coverage_gaps(json.dumps(config))
    assert "freecad_cloth/common/GarmentDocument.py" in gaps


def test_ty_warning_diagnostics_are_blocking() -> None:
    """Reject a configuration that allows warning-only ty runs to pass."""
    config_text = TY_CONFIG.read_text(encoding="utf-8")
    assert ty_warnings_are_blocking(config_text)
    tampered = config_text.replace("error-on-warning = true", "error-on-warning = false")
    assert not ty_warnings_are_blocking(tampered)
