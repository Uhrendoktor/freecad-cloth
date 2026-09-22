import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _main_guard(node):
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


def test_garment_e2e_has_explicit_main_entrypoint():
    source = (ROOT / "tests" / "freecad_garment_e2e_smoke.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    guards = [node for node in tree.body if _main_guard(node)]
    assert len(guards) == 1
    guard = guards[0]
    assert any(
        isinstance(candidate, ast.Call)
        and isinstance(candidate.func, ast.Name)
        and candidate.func.id == "run_acceptance"
        for candidate in ast.walk(guard)
    )
    for node in tree.body:
        if node is guard:
            continue
        assert not any(
            isinstance(candidate, ast.Call)
            and isinstance(candidate.func, ast.Name)
            and candidate.func.id == "run_acceptance"
            for candidate in ast.walk(node)
        )
