# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression checks for strict-quality cache identity and command coverage."""

from pathlib import Path

from tests.support.assertions import require
from tools.ci.strict_quality import (
    CPU_TORCH_REQUIREMENT,
    PIP_READ_TIMEOUT_SECONDS,
    PIP_RETRY_COUNT,
    PYTORCH_CPU_INDEX,
    build_environment_cache_key,
    quality_commands,
    quality_install_command,
    ready_marker_is_current,
)


def test_environment_cache_key_covers_all_mutable_inputs(tmp_path: Path) -> None:
    """Keep cache identity stable and invalidate it for every mutable input.

    Args:
        tmp_path: Pytest-managed directory for the temporary project manifest.
    """
    project = tmp_path / "pyproject.toml"
    project.write_text("[project]\nname = 'fixture'\n", encoding="utf-8")
    key = build_environment_cache_key(project, "3.12", "sha256:image-a", "worktree-a")
    require(
        condition=key
        == build_environment_cache_key(project, "3.12", "sha256:image-a", "worktree-a"),
        message="Identical project and runtime inputs must produce the same cache key.",
    )
    require(
        condition=key
        != build_environment_cache_key(project, "3.12", "sha256:image-b", "worktree-a"),
        message="A different runtime image must produce a different cache key.",
    )
    require(
        condition=key
        != build_environment_cache_key(project, "3.12", "sha256:image-a", "worktree-b"),
        message="A different workspace identity must produce a different cache key.",
    )
    project.write_text("[project]\nname = 'changed'\n", encoding="utf-8")
    require(
        condition=key
        != build_environment_cache_key(project, "3.12", "sha256:image-a", "worktree-a"),
        message="A changed project manifest must produce a different cache key.",
    )


def test_ready_marker_accepts_only_the_exact_environment_key(tmp_path: Path) -> None:
    """Reject absent or stale environment markers and accept the exact key.

    Args:
        tmp_path: Pytest-managed directory for the marker file.
    """
    require(
        condition=not ready_marker_is_current(tmp_path, "required-key"),
        message="An absent completion marker must not be accepted.",
    )
    (tmp_path / ".ready").write_text("stale-key\n", encoding="utf-8")
    require(
        condition=not ready_marker_is_current(tmp_path, "required-key"),
        message="A stale completion marker must not be accepted.",
    )
    (tmp_path / ".ready").write_text("required-key\n", encoding="utf-8")
    require(
        condition=ready_marker_is_current(tmp_path, "required-key"),
        message="The exact dependency/runtime key must be accepted.",
    )


def test_quality_install_command_uses_resilient_download_timeouts() -> None:
    """Allow large pinned wheels to finish without changing the development dependency set."""
    python = Path("/runner-cache/venvs/strict-quality/bin/python")
    command = quality_install_command(python)
    timeout_index = command.index("--timeout")
    retries_index = command.index("--retries")
    require(
        condition=command[timeout_index + 1] == str(PIP_READ_TIMEOUT_SECONDS),
        message="The pip socket timeout must use the explicit resilient read-timeout setting.",
    )
    require(
        condition=command[retries_index + 1] == str(PIP_RETRY_COUNT),
        message="The pip retry budget must remain explicit and testable.",
    )
    require(
        condition=PYTORCH_CPU_INDEX in command and CPU_TORCH_REQUIREMENT in command,
        message="The CPU-only Torch pin and its index must remain unchanged.",
    )
    require(
        condition=command[-2:] == ("-e", ".[dev]"),
        message="The complete development dependency set must still be installed.",
    )


def test_quality_command_inventory_includes_every_strict_gate() -> None:
    """Keep architecture, typing, documentation, workflow, and Ruff checks enabled."""
    python = Path("/runner-cache/venvs/strict-quality/bin/python")
    commands = quality_commands(python, ("freecad_cloth/module.py", "tests/module.pyi"))
    labels = {command.label for command in commands}
    arguments = tuple(command.arguments for command in commands)
    require(
        condition=labels
        == {
            "Python compilation",
            "Markdown contract",
            "CI structure",
            "Import architecture",
            "Source-rewriting policy",
            "Explicit Any policy",
            "Pydantic model policy",
            "Pyright production inventory",
            "Typed simulation core",
            "Changed Python annotation ratchet",
            "AST-grep rule tests",
            "AST-grep repository contracts",
            "Dead-code contract",
            "CrossHair contracts",
            "Pre-commit actionlint",
            "Pre-commit zizmor",
            "Pre-commit yamllint",
            "Python documentation contract",
            "Focused migration regression tests",
            "Ruff format",
            "Ruff lint",
        },
        message="The quality runner must retain every independent strict gate.",
    )
    require(
        condition=("pyright", "-p", "pyrightconfig.json") in arguments,
        message="The reviewed Pyright production inventory must remain enabled.",
    )
    require(
        condition=any(
            command[:4] == ("ty", "check", "--output-format", "github")
            for command in arguments
        ),
        message="The blocking ty simulation-core profile must remain enabled.",
    )
    require(
        condition=any(
            any("check_changed_python_types.py" in item for item in command)
            for command in arguments
        ),
        message="Changed Python annotation/object debt must not increase.",
    )
    require(
        condition=any(
            any("check_explicit_any_annotations.py" in item for item in command)
            for command in arguments
        ),
        message="The repository-wide explicit-Any policy must remain enabled.",
    )
    require(
        condition=any(
            any("check_pydantic_models.py" in item for item in command) for command in arguments
        ),
        message="Pydantic model boundary validation must remain enabled.",
    )
    focused_regression_command = (
        str(python),
        "-m",
        "pytest",
        "-q",
        "tests/test_avatar_arrangement_contract.py",
        (
            "tests/test_ci_configuration.py::"
            "test_ruff_covers_every_tracked_python_file_without_auto_fixing"
        ),
        (
            "tests/test_ci_configuration.py::"
            "test_pyright_uses_the_reviewed_staged_production_inventory"
        ),
        (
            "tests/test_ci_configuration.py::"
            "test_new_python_modules_must_be_explicitly_reviewed_for_pyright"
        ),
        (
            "tests/test_ci_configuration.py::"
            "test_ty_warning_diagnostics_remain_blocking"
        ),
        "tests/test_avatar_service_contract.py",
        "tests/test_changed_python_types.py",
        "tests/test_command_runner.py",
        "tests/test_documentation_contract.py",
        "tests/test_explicit_any_annotations.py",
        "tests/test_garment_document_contract.py",
        "tests/test_no_source_rewriting.py",
        "tests/test_pydantic_models_policy.py",
        "tests/test_sewing_creation_session.py",
        "tests/test_strict_quality_runner_contract.py",
    )
    require(
        condition=focused_regression_command in arguments,
        message="The focused migration regressions must run in the pinned quality environment.",
    )
    has_documentation_contract = any(
        "check_documentation_contract.py" in item for command in arguments for item in command
    )
    require(
        condition=has_documentation_contract,
        message="The Python documentation contract must remain enabled.",
    )
    require(
        condition=any("format" in command and "--check" in command for command in arguments),
        message="The Ruff format check must remain enabled.",
    )
    require(
        condition=any("ruff" in command and "check" in command for command in arguments),
        message="The Ruff lint check must remain enabled.",
    )
    require(
        condition=any("freecad_cloth/module.py" in command for command in arguments),
        message="The production Python source must be included in both Ruff commands.",
    )
    require(
        condition=any("tests/module.pyi" in command for command in arguments),
        message="Python stubs must remain included in both Ruff commands.",
    )
