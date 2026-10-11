"""Tests for repository Markdown link validation."""

from pathlib import Path

from tools.check_markdown_contract import ROOT, check, markdown_files


def test_all_documentation_files_have_resolvable_local_references():
    """Every local Markdown/HTML reference resolves from its source file."""
    errors = [error for path in markdown_files() for error in check(path)]
    assert errors == []


def test_documentation_contract_covers_human_and_agent_surfaces():
    """The contract includes the main human and agent documentation roots."""
    paths = {path.relative_to(ROOT).as_posix() for path in markdown_files()}

    assert {"README.md", "AGENTS.md", "docs/README.md", ".github/PULL_REQUEST_TEMPLATE.md"} <= paths


def test_documentation_navigation_has_the_expected_entry_points():
    """The documentation index exposes task-oriented routes for humans."""
    docs = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")

    for target in (
        "INSTALLATION.md",
        "EXAMPLES.md",
        "USER_GUIDE.md",
        "wiki/README.md",
        "TROUBLESHOOTING.md",
        "WORKBENCH_GUIDE.md",
    ):
        assert target in docs
