from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_agent_context_contract_stays_compact_and_current_first():
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert len(text.splitlines()) <= 110
    assert "current-state-first" in text
    assert "Closed issues/PRs, old branches, old commits, old workflow runs, and old artifacts" in text
    assert "read the smallest set of files needed" in text


def test_repository_has_one_canonical_roadmap_and_no_duplicate_packaging_proposal():
    root_roadmap = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
    assert root_roadmap.count("docs/ROADMAP.md") == 1
    assert "2026 Supervisor Replan" not in root_roadmap
    assert not (ROOT / "PACKAGING_PROPOSAL.md").exists()


def test_planning_and_live_state_documents_are_explicitly_separated():
    docs_readme = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
    research = (ROOT / "docs" / "RESEARCH.md").read_text(encoding="utf-8")
    assert "do not load the whole directory by default" in docs_readme
    assert "Issue/PR history is task-local evidence" in docs_readme
    assert "historical baseline" in roadmap
    assert "not a current implementation or release-status record" in research
