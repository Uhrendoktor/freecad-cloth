from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_review_protocol_and_templates_exist():
    workflow = (ROOT / ".github/workflows/canonical-execution.yml").read_text(encoding="utf-8")
    publisher = (ROOT / ".github/actions/publish-visual-evidence/action.yml").read_text(
        encoding="utf-8"
    )
    protocol = (ROOT / "docs/SIMULATION_REVIEW.md").read_text(encoding="utf-8")

    assert "publish-pr-simulation-evidence:" in workflow
    assert "needs: [agent-quality, gui-tunic-visual]" in workflow
    assert "needs.gui-tunic-visual.result == 'success'" in workflow
    assert "github.event_name == 'pull_request'" in workflow
    assert "mode: pr" in workflow
    assert "evidence-head: ${{ github.event.pull_request.head.sha }}" in workflow
    assert "Download PR simulation artifact" in publisher
    assert "tunic-visual-audit" in publisher
    assert "python3 tools/ci/publish_pr_simulation_evidence.py" in publisher
    assert "actual rendered PNGs" in protocol
    assert (ROOT / ".github/PULL_REQUEST_TEMPLATE/simulation-review.md").is_file()
    assert (ROOT / ".github/ISSUE_TEMPLATE/simulation-review.md").is_file()
