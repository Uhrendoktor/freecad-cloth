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


def test_only_freecad_bootstrap_python_files_remain_at_root():
    root = Path(__file__).resolve().parents[1]
    assert {path.name for path in root.glob("*.py")} <= {"Init.py", "InitGui.py"}


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
