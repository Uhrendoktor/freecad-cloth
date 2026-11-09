# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression checks for strict-quality cache identity and command coverage."""

from pathlib import Path

from tools.ci.strict_quality import (
    build_environment_cache_key,
    quality_commands,
    ready_marker_is_current,
)


def test_environment_cache_key_covers_all_mutable_inputs(tmp_path: Path) -> None:
    """Change the environment key when project, image, or workspace identity changes."""
    project = tmp_path / "pyproject.toml"
    project.write_text("[project]\nname = 'fixture'\n", encoding="utf-8")
    key = build_environment_cache_key(project, "3.12", "sha256:image-a", "worktree-a")
    assert key == build_environment_cache_key(
        project, "3.12", "sha256:image-a", "worktree-a"
    )
    assert key != build_environment_cache_key(
        project, "3.12", "sha256:image-b", "worktree-a"
    )
    assert key != build_environment_cache_key(
        project, "3.12", "sha256:image-a", "worktree-b"
    )
    project.write_text("[project]\nname = 'changed'\n", encoding="utf-8")
    assert key != build_environment_cache_key(
        project, "3.12", "sha256:image-a", "worktree-a"
    )


def test_ready_marker_accepts_only_the_exact_environment_key(tmp_path: Path) -> None:
    """Reject absent or stale completion markers and accept the matching key."""
    assert not ready_marker_is_current(tmp_path, "required-key")
    (tmp_path / ".ready").write_text("stale-key\n", encoding="utf-8")
    assert not ready_marker_is_current(tmp_path, "required-key")
    (tmp_path / ".ready").write_text("required-key\n", encoding="utf-8")
    assert ready_marker_is_current(tmp_path, "required-key")


def test_quality_command_inventory_includes_every_strict_gate() -> None:
    """Keep architecture, types, documentation, workflow and Ruff checks enabled."""
    python = Path("/runner-cache/venvs/strict-quality/bin/python")
    commands = quality_commands(python, ("freecad_cloth/module.py", "tests/module.pyi"))
    labels = {command.label for command in commands}
    arguments = tuple(command.arguments for command in commands)
    assert labels == {
        "Python compilation", "Markdown contract", "CI structure", "Import architecture",
        "Source-rewriting policy", "Strict Pyright", "AST-grep rule tests",
        "AST-grep repository contracts", "Dead-code contract", "CrossHair contracts",
        "Pre-commit actionlint", "Pre-commit zizmor", "Pre-commit yamllint",
        "Python documentation contract", "Ruff format", "Ruff lint",
    }
    assert ("pyright", "-p", "pyrightconfig.json") in arguments
    assert any("check_documentation_contract.py" in item for command in arguments for item in command)
    assert any("format" in command and "--check" in command for command in arguments)
    assert any("ruff" in command and "check" in command for command in arguments)
    assert any("freecad_cloth/module.py" in command for command in arguments)
    assert any("tests/module.pyi" in command for command in arguments)
