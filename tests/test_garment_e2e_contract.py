"""Static contracts for the canonical garment end-to-end workflow."""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _is_main_guard(node):
    return (
        isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "__name__"
        and len(node.test.ops) == 1
        and isinstance(node.test.ops[0], ast.Eq)
        and len(node.test.comparators) == 1
        and isinstance(node.test.comparators[0], ast.Constant)
        and node.test.comparators[0].value == "__main__"
    )


def test_garment_e2e_has_a_single_import_safe_entrypoint():
    source = (ROOT / "tests" / "freecad_garment_e2e_smoke.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    guards = [node for node in tree.body if _is_main_guard(node)]
    assert len(guards) == 1
    main_guard = guards[0]
    assert any(
        isinstance(candidate, ast.Call)
        and isinstance(candidate.func, ast.Name)
        and candidate.func.id == "run_acceptance"
        for candidate in ast.walk(main_guard)
    )


def test_canonical_workflow_executes_existing_pytest_style_contracts_and_e2e():
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
    assert "python3 -m pytest -q tests/test_seam_graph.py tests/test_workbench_icons.py" in workflow
    assert "gui-garment-e2e:" in workflow
    assert "/workspace/tests/freecad_garment_e2e_smoke.py" in workflow
    for marker in (
        "triangle-preflight=passed",
        "staged-selection=passed",
        "sewing-1to1=passed type=curved",
        "sewing-mn=passed sides=2,2 segments=2",
        "garment-hierarchy=passed groups=Patterns,Sewing,Fabric,Avatar,Simulation",
        "save-reload=passed pieces=4 seam=1to1 network=2segment",
        "invalidation-restore=passed seam=Valid",
        "stale-export=blocked",
        "determinism-signature=passed ",
        "pattern-export=passed formats=SVG,DXF",
        "canonical garment end-to-end acceptance passed",
    ):
        assert marker in workflow
