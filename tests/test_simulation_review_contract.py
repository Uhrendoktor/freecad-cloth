from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_simulation_review_protocol_requires_inline_screenshots():
    template = (ROOT / ".github" / "ISSUE_TEMPLATE" / "simulation_review.yml").read_text(encoding="utf-8")
    guide = (ROOT / "docs" / "SIMULATION_REVIEW.md").read_text(encoding="utf-8")
    development = (ROOT / "docs" / "DEVELOPMENT.md").read_text(encoding="utf-8")
    assert "actual PNG screenshots" in template
    assert "Artifact links alone do not satisfy review" in template
    assert "actual screenshots inline" in guide
    assert "Stop at the first failing rung" in guide
    assert "actual rendered screenshots inline" in development
    assert "artifact link by itself is not sufficient" in development


def test_one_workflow_and_root_ledger_are_preserved():
    state = (ROOT / "TOOL_STATE.md").read_text(encoding="utf-8")
    status = (ROOT / "AGENT_STATUS.md").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
    assert "supervisor_issue: 2492" in state
    assert "Root experiment ledger: #2492" in status
    assert workflow.count("name: Canonical execution") == 1
    assert "Prepare human visual review bundle" in workflow
    assert "retention-days: 14" in workflow


def test_simulation_review_template_is_diagnostic_not_a_release_gate():
    guide = (ROOT / "docs" / "SIMULATION_REVIEW.md").read_text(encoding="utf-8")
    assert "one bounded causal experiment" in guide
    assert "Solver budgets" in guide
    assert "do not carry an unproven production physics modification" in guide
