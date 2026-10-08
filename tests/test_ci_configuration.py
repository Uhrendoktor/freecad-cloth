"""Tests for the repository's single-source CI configuration contracts."""

from pathlib import Path

from tools.ci.run_freecad import configured_timeout_seconds


ROOT = Path(__file__).resolve().parents[1]


def test_freecad_timeout_is_positive_and_declared_once():
    """The application timeout comes from the project configuration."""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert configured_timeout_seconds() == 55
    assert pyproject.count("freecad_application_timeout_seconds") == 1


def test_ci_consumers_do_not_duplicate_the_application_timeout():
    """Workflow and action surfaces delegate to the project configuration."""
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    action = (ROOT / ".github" / "actions" / "freecad-test" / "action.yml").read_text(
        encoding="utf-8"
    )
    runner = (ROOT / "tools" / "ci" / "run_freecad.py").read_text(encoding="utf-8")

    assert "timeout-seconds:" not in workflow
    assert "timeout-seconds:" not in action
    assert "configured_timeout_seconds()" in runner


def test_timeout_contract_is_documented():
    """The human documentation points to the authoritative configuration."""
    docs = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    configuration = (ROOT / "docs" / "CI_CONFIGURATION.md").read_text(encoding="utf-8")

    assert "CI configuration" in docs
    assert "pyproject.toml" in configuration
    assert "freecad_application_timeout_seconds" in configuration
