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


def test_publisher_uses_checked_out_head_and_authenticated_origin():
    workflow = (ROOT / ".github/workflows/canonical-execution.yml").read_text(encoding="utf-8")
    assert 'git remote set-url origin "https://x-access-token:$GH_TOKEN@github.com/$REPOSITORY.git"' in workflow
    assert 'git worktree add --detach "$worktree" HEAD' in workflow
    assert 'git worktree add --detach "$worktree" "$GITHUB_SHA"' not in workflow
