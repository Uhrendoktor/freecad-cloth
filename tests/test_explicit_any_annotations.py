# Copyright (C) 2026 FreeCAD Cloth contributors
"""Tests for the repository-wide explicit-Any and type-check workflow policies."""

from __future__ import annotations

import json

import pytest

from tests.support.assertions import require, require_not_none
from tools.ci.check_explicit_any_annotations import (
    explicit_any_violations,
    literal_host_importlib_violations,
)
from tools.ci.validate_ci_structure import (
    PYRIGHT_CONFIG,
    PYTHON_POLICY_COMMANDS,
    TY_CONFIG,
    TYPECHECK_COMMANDS,
    WORKFLOW,
    missing_python_policy_commands,
    missing_source_rewriting_policy_commands,
    missing_typecheck_commands,
    pyright_coverage_contract_violations,
    source_rewriting_policy_tests_are_blocking,
    ty_warnings_are_blocking,
)


@pytest.mark.parametrize(
    "source",
    [
        "from typing import Any\nvalue: Any\n",
        "import typing\nvalue: dict[str, typing.Any]\n",
        "import typing as t\nvalue: list[t.Any]\n",
        "from typing import Any as Dynamic\nclass Model:\n    payload: Dynamic\n",
        "from typing_extensions import Any as Dynamic\nvalue = list[Dynamic]\n",
        "from typing import *\nvalue: Any\n",
        "from typing import Any\nAlias = dict[str, Any]\n",
    ],
)
def test_explicit_any_references_are_rejected(source: str) -> None:
    """Reject direct, renamed, qualified, wildcard, and type-alias Any usage.

    Args:
        source: Python source text with type annotations to inspect.
    """
    require(
        condition=bool(explicit_any_violations(source)),
        message="Explicit Any references in source annotations must be rejected.",
    )


@pytest.mark.parametrize(
    "source",
    [
        "from typing import Any\ndef render(value: 'Any') -> 'list[Any]':\n    return [value]\n",
        "import typing as t\ndef render(value: 't.Any') -> None:\n    return None\n",
        (
            "from typing import Any as Dynamic\n"
            "def render(value: 'Dynamic') -> None:\n"
            "    return None\n"
        ),
        "from typing import Any\ndef render(value): # type: (Any) -> Any\n    return value\n",
        "from typing import Any\nvalue = 1 # type: Any\n",
    ],
)
def test_stringified_annotations_and_type_comments_are_rejected(source: str) -> None:
    """Inspect quoted forward references and legacy type comments as type syntax.

    Args:
        source: Python source text with quoted or commented type syntax.
    """
    require(
        condition=bool(explicit_any_violations(source)),
        message="Stringified annotations and legacy type comments must reject Any.",
    )


def test_ordinary_strings_are_not_parsed_as_type_syntax() -> None:
    """Leave ordinary text strings alone even when they contain the token Any."""
    source = "from typing import Any\nmessage = 'Any'\ncaption = 'typing.Any'\n"
    require(
        condition=explicit_any_violations(source) == (),
        message="Ordinary text strings must not be parsed as type syntax.",
    )


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
    require(
        condition=explicit_any_violations(source) == (),
        message="Concrete types and protocols must pass the explicit-Any policy.",
    )


def test_parse_errors_fail_closed() -> None:
    """Do not silently skip source when the AST parser cannot read it."""
    result = explicit_any_violations("value: Any =\n", "broken.py")
    first_error = require_not_none(
        result[0] if result else None,
        message="Invalid source syntax must produce a diagnostic.",
    )
    require(
        condition=first_error.startswith("broken.py:1: invalid Python syntax"),
        message="Parse diagnostics must identify the source path and line.",
    )


@pytest.mark.parametrize(
    "source",
    [
        'import importlib\\napp = importlib.import_module("FreeCAD")',
        'import importlib as loader\\napp = loader.import_module("FreeCADGui")',
        'from importlib import import_module as load\\napp = load("FreeCAD")',
    ],
)
def test_literal_freecad_modules_cannot_be_loaded_through_importlib(source: str) -> None:
    """Reject fixed FreeCAD module names passed through importlib.

    Args:
        source: Python source that calls importlib with a constant host module name.
    """
    require(
        condition=bool(literal_host_importlib_violations(source)),
        message="Fixed FreeCAD host modules must use explicit imports or dependency injection.",
    )


@pytest.mark.parametrize(
    "source",
    [
        "import importlib\\napp = importlib.import_module(module_name)",
        'import importlib\\nmodule = importlib.import_module("freecad_cloth.pattern.workbench")',
        'import importlib\\nqt = importlib.import_module("PySide.QtCore")',
        'message = "importlib.import_module(\\\"FreeCAD\\\")"',
    ],
)
def test_dynamic_and_non_host_importlib_loading_remains_supported(source: str) -> None:
    """Allow runtime-selected modules, other modules, and ordinary strings.

    Args:
        source: Python source that should not violate the fixed host-module policy.
    """
    require(
        condition=literal_host_importlib_violations(source) == (),
        message="Only literal FreeCAD and FreeCADGui importlib calls are prohibited.",
    )


def test_canonical_workflow_contains_all_blocking_type_gates() -> None:
    """Require one blocking Pyright config covering every repository Python file."""
    workflow_text = WORKFLOW.read_text(encoding="utf-8")
    require(
        condition=missing_typecheck_commands(workflow_text) == (),
        message="All blocking type checks must remain in the workflow.",
    )
    require(
        condition=missing_python_policy_commands(workflow_text) == (),
        message="All Python policy checks must remain in the workflow.",
    )
    require(
        condition=missing_source_rewriting_policy_commands(workflow_text) == (),
        message="Source-rewriting checks must remain in the workflow.",
    )
    require(
        condition=source_rewriting_policy_tests_are_blocking(workflow_text),
        message="Source-rewriting policy tests must be blocking.",
    )
    require(
        condition=workflow_text.count("pyright -p pyrightconfig.json") == 1,
        message="The standard repository-wide Pyright gate must occur once.",
    )
    require(
        condition="pyrightconfig.agent-strict.json" not in workflow_text,
        message="The workflow must not reference a temporary strict config.",
    )
    config = json.loads(PYRIGHT_CONFIG.read_text(encoding="utf-8"))
    require(
        condition=config["typeCheckingMode"] == "standard",
        message="Pyright must use standard mode for the repository inventory.",
    )
    require(
        condition=config["strict"]
        == [
            "freecad_cloth/simulation/DrapeFailureClassifier.py",
            "freecad_cloth/simulation/cloth_backend.py",
            "freecad_cloth/simulation/ClothSolver.py",
        ],
        message="Only the reviewed simulation modules may use strict-mode overrides.",
    )
    require(
        condition=not PYRIGHT_CONFIG.with_name("pyrightconfig.agent-strict.json").exists(),
        message="The temporary strict config must not exist.",
    )


@pytest.mark.parametrize("command", TYPECHECK_COMMANDS)
def test_type_gate_contract_detects_removed_command(command: str) -> None:
    """Catch a workflow regression if any blocking type gate is removed.

    Args:
        command: Exact type-check command whose removal is simulated.
    """
    workflow_text = WORKFLOW.read_text(encoding="utf-8")
    tampered = workflow_text.replace(command, "", 1)
    require(
        condition=missing_typecheck_commands(tampered) == (command,),
        message="Removing one type gate must report precisely that command.",
    )


@pytest.mark.parametrize("command", PYTHON_POLICY_COMMANDS)
def test_python_policy_contract_detects_removed_command(command: str) -> None:
    """Prevent removal of the production Pydantic policy.

    Args:
        command: Exact Python policy command whose removal is simulated.
    """
    workflow_text = WORKFLOW.read_text(encoding="utf-8")
    tampered = workflow_text.replace(command, "", 1)
    require(
        condition=missing_python_policy_commands(tampered) == (command,),
        message="Removing one Python policy command must be detected.",
    )


def test_pyright_coverage_matches_the_reviewed_staged_inventory() -> None:
    """Keep the reviewed include/exclude inventory stable until errors are triaged."""
    config_text = PYRIGHT_CONFIG.read_text(encoding="utf-8")
    require(
        condition=pyright_coverage_contract_violations(config_text) == (),
        message="The reviewed Pyright inventory must satisfy the coverage contract.",
    )


def test_pyright_coverage_guard_detects_a_narrowed_include_set() -> None:
    """Catch future edits that silently reduce the Pyright include set."""
    config = json.loads(PYRIGHT_CONFIG.read_text(encoding="utf-8"))
    config["include"] = ["freecad_cloth/simulation/cloth_backend.py"]
    violations = pyright_coverage_contract_violations(json.dumps(config))
    require(
        condition=violations == ("<Pyright include scope must cover the entire repository>",),
        message="A narrowed Pyright include list must be rejected.",
    )


def test_new_production_modules_cannot_escape_pyright_scope() -> None:
    """Ensure new production modules remain inside repository-wide Pyright analysis."""
    config_text = PYRIGHT_CONFIG.read_text(encoding="utf-8")
    new_modules = (
        "freecad_cloth/common/new_model.py",
        "freecad_cloth/simulation/NewSimulationGui.py",
        "freecad_cloth/bootstrap.py",
        "freecad_cloth/pattern/NewPatternFeature.py",
    )

    require(
        condition=pyright_coverage_contract_violations(config_text, new_modules) == (),
        message="New production modules must remain covered by Pyright.",
    )


def test_pyright_coverage_guard_rejects_explicit_exclusions() -> None:
    """Prevent a future exclude list from skipping repository Python files."""
    config = json.loads(PYRIGHT_CONFIG.read_text(encoding="utf-8"))
    config["exclude"] = ["tests/**"]
    require(
        condition=pyright_coverage_contract_violations(json.dumps(config))
        == ("<Pyright exclude scope must not narrow repository coverage>",),
        message="Explicit exclusions must not narrow repository-wide Pyright coverage.",
    )


def test_typecheck_commands_must_be_standalone_blocking_steps() -> None:
    """Reject a shell chain that can mask a type checker's nonzero status."""
    workflow_text = WORKFLOW.read_text(encoding="utf-8")
    chained = workflow_text.replace(
        "          pyright -p pyrightconfig.json\n",
        (
            "          python tools/ci/check_explicit_any_annotations.py && "
            "pyright -p pyrightconfig.json\n"
        ),
        1,
    )
    missing = missing_typecheck_commands(chained)
    require(
        condition=missing == ("pyright -p pyrightconfig.json",),
        message="A chained command must not mask the type-check exit status.",
    )


def test_ty_warning_diagnostics_are_blocking() -> None:
    """Reject a configuration that allows warning-only ty runs to pass."""
    config_text = TY_CONFIG.read_text(encoding="utf-8")
    require(
        condition=ty_warnings_are_blocking(config_text),
        message="ty warnings must fail the policy gate.",
    )
    tampered = config_text.replace("error-on-warning = true", "error-on-warning = false")
    require(
        condition=not ty_warnings_are_blocking(tampered),
        message="The guard must reject warning-only ty configuration.",
    )
