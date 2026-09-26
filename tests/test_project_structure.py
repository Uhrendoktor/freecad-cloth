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
    user_guide = root / "docs" / "USER_GUIDE.md"
    docs_readme = root / "docs" / "README.md"
    assert user_guide.is_file()
    assert "USER_GUIDE.md" in docs_readme.read_text(encoding="utf-8")
def test_canonical_workflow_pr_validation_contract():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
    assert "pull_request:" in workflow
    assert "pull_request_target:" not in workflow
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


def test_blanket_evidence_validates_after_docker_restore():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
    block = workflow.split("  gui-visual-examples:", 1)[1].split("  publish-readme-turntables:", 1)[0]
    restore = block.index("name: Restore workspace from Docker volume")
    validate = block.index("name: Validate blanket visual evidence")
    assert restore < validate



def test_turntable_frame_counts_validate_after_restore():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
    block = workflow.split("  gui-turntables:", 1)[1].split("  gui-visual-examples:", 1)[0]
    restore = block.index("name: Restore workspace from Docker volume")
    validate = block.index("name: Validate turntable frame counts on restored workspace")
    assert restore < validate


def test_canonical_workflow_keeps_simple_local_first_fallback():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
    assert "runner_watchdog:" in workflow
    assert "runner-watchdog=fallback" in workflow
    assert "-f runner_mode=hosted" in workflow
    assert "-f fallback_source_run=" in workflow
    assert "pull_request_broker:" not in workflow
    assert "runner_router:" not in workflow
    assert "runner_heartbeat:" not in workflow
    assert "sketcher-startup-diagnostic:" not in workflow
    assert "*/5 * * * *" not in workflow
