# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression checks for strict-quality cache identity and command coverage."""

from pathlib import Path

from tests.support.assertions import require
from tools.ci.strict_quality import (
    build_environment_cache_key,
    quality_commands,
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
        condition=key == build_environment_cache_key(
            project, "3.12", "sha256:image-a", "worktree-a"
        ),
        message="Identical project and runtime inputs must produce the same cache key.",
    )
    require(
        condition=key != build_environment_cache_key(
            project, "3.12", "sha256:image-b", "worktree-a"
        ),
        message="A different runtime image must produce a different cache key.",
    )
    require(
        condition=key != build_environment_cache_key(
            project, "3.12", "sha256:image-a", "worktree-b"
        ),
        message="A different workspace identity must produce a different cache key.",
    )
    project.write_text("[project]\nname = 'changed'\n", encoding="utf-8")
    require(
        condition=key != build_environment_cache_key(
            project, "3.12", "sha256:image-a", "worktree-a"
        ),
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
            "Strict Pyright",
            "AST-grep rule tests",
            "AST-grep repository contracts",
            "Dead-code contract",
            "CrossHair contracts",
            "Pre-commit actionlint",
            "Pre-commit zizmor",
            "Pre-commit yamllint",
            "Python documentation contract",
            "Ruff format",
            "Ruff lint",
        },
        message="The quality runner must retain every independent strict gate.",
    )
    require(
        condition=("pyright", "-p", "pyrightconfig.json") in arguments,
        message="The strict whole-repository Pyright command must remain enabled.",
    )
    require(
        condition=any("check_documentation_contract.py" in item for command in arguments for item in command),
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
