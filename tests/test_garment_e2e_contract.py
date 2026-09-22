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


def test_garment_e2e_does_not_execute_acceptance_when_imported():
    source = (ROOT / "tests" / "freecad_garment_e2e_smoke.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    guards = [node for node in tree.body if _is_main_guard(node)]
    assert len(guards) == 1
    main_guard = guards[0]
    for node in tree.body:
        if node is main_guard:
            continue
        assert not any(
            isinstance(candidate, ast.Call)
            and isinstance(candidate.func, ast.Name)
            and candidate.func.id == "run_acceptance"
            for candidate in ast.walk(node)
        ), "run_acceptance() must not execute during module import"
    assert any(
        isinstance(candidate, ast.Call)
        and isinstance(candidate.func, ast.Name)
        and candidate.func.id == "run_acceptance"
        for candidate in ast.walk(main_guard)
    ), "main guard must invoke the acceptance entry point"
