from pathlib import Path
import re


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



def test_agent_instructions_use_live_ledger_pointer_without_hardcoding_an_issue():
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "current coordination ledger named in" in text
    assert not re.search(r"#\d+", text)


def test_architecture_distinguishes_persisted_authority_from_headless_value_types():
    architecture = (ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    model = (ROOT / "freecad_cloth" / "pattern" / "PatternModel.py").read_text(encoding="utf-8")
    assert "persisted FreeCAD Seam object is the document-level source of truth" in architecture
    assert "canonical immutable in-memory/value representation" in architecture
    assert "persisted" in model and "in-memory/headless" in model


def test_historical_planning_docs_do_not_present_closed_issues_as_active_work():
    feature_matrix = (ROOT / "docs" / "FEATURE_MATRIX.md").read_text(encoding="utf-8")
    library = (ROOT / "docs" / "LIBRARY_EVALUATION.md").read_text(encoding="utf-8")
    benchmark = (ROOT / "docs" / "BENCHMARK_DRIVEN_IMPROVEMENTS.md").read_text(encoding="utf-8")
    assert "not an implementation checklist" in feature_matrix
    assert "Those issues are closed" in library
    assert "not a live task list" in benchmark



def test_live_coordination_documents_do_not_hardcode_a_specific_issue():
    for path in (ROOT / "README.md", ROOT / "docs" / "DEVELOPMENT.md", ROOT / ".github" / "ISSUE_TEMPLATE" / "simulation-review.md"):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"#\d+", text)
        assert "AGENT_STATUS.md" in text


def test_development_guide_points_to_the_canonical_prompt_schema():
    root = ROOT / "docs" / "DEVELOPMENT.md"
    text = root.read_text(encoding="utf-8")
    assert "seven-field prompt contract in the root `AGENTS.md`" in text
    assert "1. Objective." not in text
    assert "2. Current evidence and exact commit/head." not in text
    assert "7. Falsifier or stop condition." not in text


def test_path_specific_agent_instructions_are_narrow_and_scoped():
    root = ROOT / ".github" / "instructions"
    simulation = (root / "simulation.instructions.md").read_text(encoding="utf-8")
    workflows = (root / "workflows.instructions.md").read_text(encoding="utf-8")
    for text, marker in ((simulation, "freecad_cloth/simulation"), (workflows, ".github/workflows")):
        assert text.startswith("---\napplyTo:")
        assert marker in text
        assert len(text.splitlines()) <= 14
    assert "AGENTS.md" not in simulation
    assert "AGENTS.md" not in workflows
