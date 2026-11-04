# Copyright (C) 2026 FreeCAD Cloth contributors
"""Contracts for native Sketcher acceptance bootstrap.

The GUI acceptance relies on FreeCAD startup to register the staged workbench
and does not use module-discovery flags.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _acceptance_job(workflow: str) -> str:
    """Extract the canonical GUI simple-acceptance workflow job.

    Args:
        workflow: Complete canonical workflow YAML.

    Returns:
        The source text defining the ``gui-simple`` job.

    """
    start = workflow.index("  gui-simple:")
    end = workflow.find("\n  gui-tunic-visual:", start)
    if end == -1:
        end = len(workflow)
    return workflow[start:end]


def test_sketcher_acceptance_uses_freecad_startup_workbench_registration() -> None:
    """Verify the Sketcher acceptance relies on FreeCAD startup registration."""
    source = (ROOT / "tests" / "freecad_sketcher_acceptance.py").read_text(encoding="utf-8")
    assert (
        "def _bootstrap_workbenches():" in source
    ), "Sketcher acceptance must provide the startup workbench bootstrap."
    assert (
        'if "ClothPatternWorkbench" not in Gui.listWorkbenches()' in source
    ), "Sketcher acceptance must verify startup registration."
    assert (
        "ClothPatternWorkbench was not loaded by FreeCAD startup" in source
    ), "The startup registration failure must remain explicit."
    assert (
        "compile(init_gui.read_text" not in source
    ), "Sketcher acceptance must not compile InitGui.py as a manual fallback."


def test_canonical_sketcher_acceptance_uses_apprun_without_module_discovery_flags() -> None:
    """Verify canonical Sketcher acceptance uses AppRun and avoids discovery flags."""
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    job = _acceptance_job(workflow)
    assert (
        "freecad-test@" in job
    ), "Canonical Sketcher acceptance must use the FreeCAD test action."
    assert (
        "tests/freecad_sketcher_acceptance.py" in job
    ), "Canonical Sketcher acceptance must select its dedicated test script."
    assert (
        "-M /tmp/freecad-mod" not in job
    ), "Canonical Sketcher acceptance must not pass the -M module discovery flag."
    assert (
        "-P /tmp/freecad-mod/freecad-cloth" not in job
    ), "Canonical Sketcher acceptance must not pass the -P module path flag."
    assert (
        (
        "validate-command: python3 tools/ci/validate_acceptance.py ${{ matrix.case }}"
        not in job
        )
    ), "Sketcher acceptance must use the canonical GUI runner, not a direct command."
