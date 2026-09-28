from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_review_protocol_and_templates_exist():
    workflow = (ROOT / ".github/workflows/canonical-execution.yml").read_text(encoding="utf-8")
    protocol = (ROOT / "docs/SIMULATION_REVIEW.md").read_text(encoding="utf-8")
    assert "gh pr comment" in workflow
    assert "simulation-evidence/pr-$PR_NUMBER" in workflow
    assert "actual rendered PNG screenshots" in protocol
    assert (ROOT / ".github/PULL_REQUEST_TEMPLATE/simulation-review.md").is_file()
    assert (ROOT / ".github/ISSUE_TEMPLATE/simulation-review.md").is_file()

