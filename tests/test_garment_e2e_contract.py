import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_garment_e2e_does_not_execute_acceptance_when_imported():
    source = (ROOT / "tests" / "freecad_garment_e2e_smoke.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    top_level_calls = [
        node.value.func.id
        for node in tree.body
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
    ]
    assert "run_acceptance" not in top_level_calls
    assert any(
        isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "__name__"
        for node in tree.body
    )
