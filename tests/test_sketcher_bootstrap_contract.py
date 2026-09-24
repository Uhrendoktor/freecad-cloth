"""Contracts for native Sketcher acceptance bootstrap.

The GUI acceptance must bootstrap the repository workbenches explicitly from
InitGui.py and must not rely on FreeCAD -M/-P module discovery.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _acceptance_job(workflow: str) -> str:
    start = workflow.index("  gui-sketcher-acceptance:")
    end = workflow.find("\n  gui-", start + 1)
    if end == -1:
        end = len(workflow)
    return workflow[start:end]


def test_sketcher_acceptance_bootstraps_repository_initgui_before_document_setup():
    source = (ROOT / "tests" / "freecad_sketcher_acceptance.py").read_text(encoding="utf-8")

    assert "def _bootstrap_workbenches():" in source
    assert 'init_gui = root / "InitGui.py"' in source
    assert 'exec(compile(init_gui.read_text(encoding="utf-8"), str(init_gui), "exec"), namespace, namespace)' in source
    assert 'if "ClothPatternWorkbench" not in Gui.listWorkbenches()' in source
    assert 'raise RuntimeError("ClothPatternWorkbench was not registered by InitGui.py")' in source

    bootstrap_index = source.index("_bootstrap_workbenches()")
    document_index = source.index('App.newDocument("NativeSketcherAcceptance")')
    assert bootstrap_index < document_index


def test_canonical_sketcher_acceptance_uses_apprun_without_module_discovery_flags():
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
    job = _acceptance_job(workflow)

    assert "/opt/freecad/AppRun" in job
    assert "tests/freecad_sketcher_acceptance.py" in job
    assert "-M /tmp/freecad-mod" not in job
    assert "-P /tmp/freecad-mod/freecad-cloth" not in job
    assert "8m" in job
    assert 'grep -q "native Sketcher acceptance passed"' in job
