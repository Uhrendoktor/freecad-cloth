"""Structural checks for the canonical Python package tree."""
from pathlib import Path


def test_project_metadata_exists():
    root = Path(__file__).resolve().parents[1]
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert "[project]" in text
    assert "name = \"freecad-cloth\"" in text
    assert "[build-system]" in text


def test_workbench_package_boundaries_exist():
    root = Path(__file__).resolve().parents[1]
    for name in ("pattern", "sewing", "simulation", "avatar", "common", "shared"):
        package = root / "freecad_cloth" / name
        assert (package / "__init__.py").is_file()
    for name in ("pattern", "sewing", "simulation"):
        assert (root / "freecad_cloth" / name / "workbench.py").is_file()


def test_only_bootstrap_python_files_remain_at_root():
    root = Path(__file__).resolve().parents[1]
    assert {path.name for path in root.glob("*.py")} <= {"Init.py", "InitGui.py", "sitecustomize.py"}


def test_freecad_entry_points_remain_at_root():
    root = Path(__file__).resolve().parents[1]
    assert (root / "Init.py").is_file()
    assert (root / "InitGui.py").is_file()
    gui = (root / "InitGui.py").read_text(encoding="utf-8")
    assert "Gui.addWorkbench(ClothPatternWorkbench())" in gui
    assert "Gui.addWorkbench(ClothSewingWorkbench())" in gui
    assert "Gui.addWorkbench(ClothSimulationWorkbench())" in gui


def test_shared_contract_is_freecad_independent():
    from freecad_cloth.shared.targets import CollisionSurface, DrapeTargetRef

    surface = CollisionSurface("human", "Avatar", revision=3)
    target = DrapeTargetRef("freecad", "Body", revision=2)
    assert surface.revision == 3
    assert target.is_freecad_object()
    assert not target.is_human()


def test_human_documentation_contract():
    root = Path(__file__).resolve().parents[1]
    getting_started = root / "docs" / "GETTING_STARTED.md"
    user_guide = root / "docs" / "USER_GUIDE.md"
    docs_readme = root / "docs" / "README.md"
    assert getting_started.is_file()
    assert user_guide.is_file()
    readme = docs_readme.read_text(encoding="utf-8")
    assert "GETTING_STARTED.md" in readme
    assert "USER_GUIDE.md" in readme
def test_canonical_workflow_pr_validation_contract():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
    assert "pull_request:" in workflow
    assert "types: [opened, synchronize, reopened]" in workflow
    assert "push:" in workflow
    assert "branches: [main]" in workflow



def test_workbench_benchmark_merge_script_is_checked_in():
    root = Path(__file__).resolve().parents[1]
    script = root / "tools" / "merge_workbench_benchmark.py"
    assert script.is_file()
    source = script.read_text(encoding="utf-8")
    assert 'names = ["Pattern", "Sewing", "Simulation"]' in source
    assert "benchmark.json" in source
