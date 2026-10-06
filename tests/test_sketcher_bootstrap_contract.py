"""Contracts for native Sketcher acceptance bootstrap.

The GUI acceptance relies on FreeCAD startup to register the staged workbench and does not use module-discovery flags.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _acceptance_job(workflow: str) -> str:
    start = workflow.index("  gui-simple:")
    end = workflow.find("\n  gui-tunic-visual:", start)
    if end == -1:
        end = len(workflow)
    return workflow[start:end]

def test_sketcher_acceptance_uses_freecad_startup_workbench_registration():
    source = (ROOT / "tests" / "freecad_sketcher_acceptance.py").read_text(encoding="utf-8")
    assert "def _bootstrap_workbenches():" in source
    assert 'if "ClothPatternWorkbench" not in Gui.listWorkbenches()' in source
    assert "ClothPatternWorkbench was not loaded by FreeCAD startup" in source
    assert "compile(init_gui.read_text" not in source

def test_canonical_sketcher_acceptance_uses_apprun_without_module_discovery_flags():
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    job = _acceptance_job(workflow)
    assert "freecad-test@" in job
    assert "tests/freecad_sketcher_acceptance.py" in job
    assert "-M /tmp/freecad-mod" not in job
    assert "-P /tmp/freecad-mod/freecad-cloth" not in job
    assert "timeout-seconds:" in job
    assert "native Sketcher acceptance passed" in job
