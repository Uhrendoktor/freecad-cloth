# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression guard for the pull-request simulation-review evidence contract."""

from pathlib import Path

from tests.support.assertions import require

ROOT = Path(__file__).resolve().parents[1]


def test_review_protocol_and_templates_exist() -> None:
    """Keep simulation-review workflow triggers, publisher behavior, and templates aligned."""
    workflow = (ROOT / ".github/workflows/canonical-execution.yml").read_text(encoding="utf-8")
    publisher = (ROOT / ".github/actions/publish-visual-evidence/action.yml").read_text(
        encoding="utf-8"
    )
    protocol = (ROOT / "docs/developers/SIMULATION_REVIEW.md").read_text(encoding="utf-8")

    require(
        condition="publish-pr-simulation-evidence:" in workflow,
        message="The canonical workflow must expose the PR simulation-evidence publisher.",
    )
    require(
        condition="needs: [agent-quality, gui-tunic-visual]" in workflow,
        message="PR simulation evidence must depend on static checks and the tunic visual audit.",
    )
    require(
        condition="needs.gui-tunic-visual.result == 'success'" in workflow,
        message="Evidence publication must require a successful tunic visual audit.",
    )
    require(
        condition="github.event_name == 'pull_request'" in workflow,
        message="The simulation-evidence publisher must be scoped to pull requests.",
    )
    require(
        condition="mode: pr" in workflow,
        message="The publisher must select the PR-specific evidence mode.",
    )
    require(
        condition="evidence-head: ${{ github.event.pull_request.head.sha || github.sha }}" in workflow,
        message="Evidence must be attributed to the exact pull-request head SHA.",
    )
    require(
        condition="Download PR simulation artifact" in publisher,
        message="The shared publisher must retrieve the PR simulation artifact.",
    )
    require(
        condition="tunic-visual-audit" in publisher,
        message="The publisher must identify the source tunic visual audit.",
    )
    require(
        condition="python3 tools/ci/publish_pr_simulation_evidence.py" in publisher,
        message="The publisher must invoke the PR evidence validator and copier.",
    )
    require(
        condition="actual rendered PNGs" in protocol,
        message="The review protocol must require actual rendered PNG evidence.",
    )
    require(
        condition=(ROOT / ".github/PULL_REQUEST_TEMPLATE/simulation-review.md").is_file(),
        message="A simulation-review pull-request template must be present.",
    )
    require(
        condition=(ROOT / ".github/ISSUE_TEMPLATE/simulation-review.md").is_file(),
        message="A simulation-review issue template must be present.",
    )
