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



def test_seam_graph_has_one_canonical_implementation():
    root = Path(__file__).resolve().parents[1]
    assert (root / "freecad_cloth" / "sewing" / "SeamGraph.py").is_file()
    assert not (root / "freecad_cloth" / "pattern" / "SeamGraph.py").exists()


def test_pattern_domain_does_not_import_seam_reference_through_compatibility_namespace():
    root = Path(__file__).resolve().parents[1]
    offenders = []
    for path in root.glob("freecad_cloth/**/*.py"):
        if path.as_posix().endswith("freecad_cloth/sewing/SeamReference.py"):
            continue
        source = path.read_text(encoding="utf-8")
        if "from freecad_cloth.sewing.SeamReference import" in source:
            offenders.append(path.as_posix())
    assert not offenders, offenders




def test_workflow_actions_use_immutable_release_pins():
    import re

    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
    pins = dict(re.findall(r"uses: (actions/(?:checkout|upload-artifact|download-artifact)|docker/login-action)@([0-9a-f]{40}) # (v[0-9.]+)", workflow))
    assert pins == {
        "actions/checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",
        "actions/upload-artifact": "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
        "actions/download-artifact": "3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c",
        "docker/login-action": "dbcb813823bdd20940b903addbd779551569679f",
    }

def test_modern_loader_does_not_mutate_sys_path():
    root = Path(__file__).resolve().parents[1]
    source = (root / "freecad" / "freecad_cloth" / "init_gui.py").read_text(encoding="utf-8")
    assert "sys.path" not in source


def test_ci_tissu_hook_is_explicit_and_has_no_import_time_pip_install():
    root = Path(__file__).resolve().parents[1]
    source = (root / "sitecustomize.py").read_text(encoding="utf-8")
    assert "CLOTH_CI_ENABLE_TISSU" in source
    assert 'os.environ.get("DISPLAY") == ":99"' in source
    assert 'os.environ.get("CLOTH_CI_ENABLE_TISSU", "0") == "1"' in source
    assert '"pip"' not in source

def test_freecad_classic_and_modern_loader_surfaces_are_documented_and_aligned():
    root = Path(__file__).resolve().parents[1]
    classic = (root / "InitGui.py").read_text(encoding="utf-8")
    modern = (root / "freecad" / "freecad_cloth" / "init_gui.py").read_text(encoding="utf-8")
    for workbench in ("ClothPatternWorkbench", "ClothSewingWorkbench", "ClothSimulationWorkbench"):
        assert workbench in classic
        assert workbench in modern
    assert "loader layouts" in (root / "docs" / "PROJECT_STRUCTURE.md").read_text(encoding="utf-8").lower()
