import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_fitting_proxy_execute_does_not_sync_derived_visuals():
    source = (ROOT / "freecad_cloth" / "avatar" / "FittingCommands.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    proxy = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "_FittingProxy")
    execute = next(node for node in proxy.body if isinstance(node, ast.FunctionDef) and node.name == "execute")
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_sync_visuals"
        for node in ast.walk(execute)
    )


def test_fitting_public_commands_keep_sync_visuals_calls():
    source = (ROOT / "freecad_cloth" / "avatar" / "FittingCommands.py").read_text(encoding="utf-8")
    assert "_sync_visuals(scene)" in source
