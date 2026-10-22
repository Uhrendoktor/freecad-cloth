# Copyright (C) 2026 FreeCAD Cloth contributors
"""Contracts for native Sketcher acceptance bootstrap.

The GUI acceptance relies on FreeCAD startup to register the staged workbench
and does not use module-discovery flags.
"""

from pathlib import Path

from tests.support.assertions import require, require_contains

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
    source = (ROOT / "tests" / "freecad_sketcher_acceptance.py").read_text(
        encoding="utf-8"
    )
    require_contains(
        source=source,
        fragment="def _bootstrap_workbenches():",
        message="Sketcher acceptance must provide the startup workbench bootstrap.",
    )
    require_contains(
        source=source,
        fragment='if "ClothPatternWorkbench" not in Gui.listWorkbenches()',
        message="Sketcher acceptance must verify startup registration.",
    )
    require_contains(
        source=source,
        fragment="ClothPatternWorkbench was not loaded by FreeCAD startup",
        message="The startup registration failure must remain explicit.",
    )
    require(
        condition="compile(init_gui.read_text" not in source,
        message="Sketcher acceptance must not compile InitGui.py as a manual fallback.",
    )


def test_canonical_sketcher_acceptance_uses_apprun_without_module_discovery_flags() -> None:
    """Verify canonical Sketcher acceptance uses AppRun and avoids discovery flags."""
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    job = _acceptance_job(workflow)
    require_contains(
        source=job,
        fragment="freecad-test@",
        message="Canonical Sketcher acceptance must use the FreeCAD test action.",
    )
    require_contains(
        source=job,
        fragment="tests/freecad_sketcher_acceptance.py",
        message="Canonical Sketcher acceptance must select its dedicated test script.",
    )
    require(
        condition="-M /tmp/freecad-mod" not in job,
        message="Canonical Sketcher acceptance must not pass the -M module discovery flag.",
    )
    require(
        condition="-P /tmp/freecad-mod/freecad-cloth" not in job,
        message="Canonical Sketcher acceptance must not pass the -P module path flag.",
    )
    require(
        condition=(
            "validate-command: python3 tools/ci/validate_acceptance.py ${{ matrix.case }}"
            not in job
        ),
        message="Sketcher acceptance must use the canonical GUI runner, not a direct command.",
    )
