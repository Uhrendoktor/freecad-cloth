"""Tests for the repository-wide explicit-Any and type-check workflow policies."""

from __future__ import annotations

import json

import pytest

from tools.ci.check_explicit_any_annotations import explicit_any_violations
from tools.ci.validate_ci_structure import (
    PYRIGHT_CONFIG,
    PYTHON_POLICY_COMMANDS,
    TY_CONFIG,
    TYPECHECK_COMMANDS,
    WORKFLOW,
    missing_python_policy_commands,
    missing_source_rewriting_policy_commands,
    source_rewriting_policy_tests_are_blocking,
    missing_typecheck_commands,
    pyright_coverage_contract_violations,
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
    """Require one Pyright config with focused strict modules and blocking gates."""
    workflow_text = WORKFLOW.read_text(encoding="utf-8")
    assert missing_typecheck_commands(workflow_text) == ()
    assert missing_python_policy_commands(workflow_text) == ()
    assert missing_source_rewriting_policy_commands(workflow_text) == ()
    assert source_rewriting_policy_tests_are_blocking(workflow_text)
    assert workflow_text.count("pyright -p pyrightconfig.json") == 1
    assert "pyrightconfig.agent-strict.json" not in workflow_text
    config = json.loads(PYRIGHT_CONFIG.read_text(encoding="utf-8"))
    assert config["typeCheckingMode"] == "standard"
    assert config["strict"] == [
        "freecad_cloth/simulation/DrapeFailureClassifier.py",
        "freecad_cloth/simulation/ClothBackend.py",
        "freecad_cloth/simulation/ClothSolver.py",
    ]
    assert not PYRIGHT_CONFIG.with_name("pyrightconfig.agent-strict.json").exists()


@pytest.mark.parametrize("command", TYPECHECK_COMMANDS)
def test_type_gate_contract_detects_removed_command(command: str) -> None:
    """Catch a workflow regression if any blocking type gate is removed."""
    workflow_text = WORKFLOW.read_text(encoding="utf-8")
    tampered = workflow_text.replace(command, "", 1)
    assert missing_typecheck_commands(tampered) == (command,)


@pytest.mark.parametrize("command", PYTHON_POLICY_COMMANDS)
def test_python_policy_contract_detects_removed_command(command: str) -> None:
    """Prevent removal of the production Pydantic policy."""
    workflow_text = WORKFLOW.read_text(encoding="utf-8")
    tampered = workflow_text.replace(command, "", 1)
    assert missing_python_policy_commands(tampered) == (command,)


def test_pyright_coverage_matches_the_reviewed_staged_inventory() -> None:
    """Keep the reviewed include/exclude inventory stable until errors are triaged."""
    config_text = PYRIGHT_CONFIG.read_text(encoding="utf-8")
    assert pyright_coverage_contract_violations(config_text) == ()


def test_pyright_coverage_guard_detects_a_narrowed_include_set() -> None:
    """Catch future edits that silently reduce the Pyright include set."""
    config = json.loads(PYRIGHT_CONFIG.read_text(encoding="utf-8"))
    config["include"] = ["freecad_cloth/simulation/ClothBackend.py"]
    violations = pyright_coverage_contract_violations(json.dumps(config))
    assert violations == ("<Pyright include scope differs from the reviewed inventory>",)


def test_new_production_modules_cannot_escape_pyright_scope() -> None:
    """Require new modules to be included in Pyright or intentionally excluded."""
    config_text = PYRIGHT_CONFIG.read_text(encoding="utf-8")

    assert (
        pyright_coverage_contract_violations(
            config_text,
            ("freecad_cloth/common/new_model.py", "freecad_cloth/simulation/NewSimulationGui.py"),
        )
        == ()
    )
    assert pyright_coverage_contract_violations(
        config_text, ("freecad_cloth/pattern/NewPatternFeature.py",)
    ) == (
        "<new Python module is outside Pyright include/exclude scope: "
        "freecad_cloth/pattern/NewPatternFeature.py>",
    )


def test_typecheck_commands_must_be_standalone_blocking_steps() -> None:
    """Reject a shell chain that can mask a type checker's nonzero status."""
    workflow_text = WORKFLOW.read_text(encoding="utf-8")
    chained = workflow_text.replace(
        "          pyright -p pyrightconfig.json\n",
        "          python tools/ci/check_explicit_any_annotations.py && pyright -p pyrightconfig.json\n",
        1,
    )
    missing = missing_typecheck_commands(chained)
    assert missing == ("pyright -p pyrightconfig.json",)


def test_ty_warning_diagnostics_are_blocking() -> None:
    """Reject a configuration that allows warning-only ty runs to pass."""
    config_text = TY_CONFIG.read_text(encoding="utf-8")
    assert ty_warnings_are_blocking(config_text)
    tampered = config_text.replace("error-on-warning = true", "error-on-warning = false")
    assert not ty_warnings_are_blocking(tampered)
