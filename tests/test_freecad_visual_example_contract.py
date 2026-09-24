"""Static contract for the blanket visual harness startup boundary."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests" / "freecad_visual_examples.py"


def _functions(tree):
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }


def _called_names(node):
    return [
        call.func.id
        for call in ast.walk(node)
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
    ]


def test_blanket_harness_bootstraps_initgui_only_when_pattern_workbench_is_absent():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    functions = _functions(tree)
    ensure = functions["_ensure_workbench_registration"]

    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "exec"
        for node in ast.walk(ensure)
    )
    assert any(
        isinstance(node, ast.Constant) and node.value == "InitGui.py"
        for node in ast.walk(ensure)
    )

    tests_for_absence = [
        node
        for node in ast.walk(ensure)
        if isinstance(node, ast.Compare)
        and any(
            isinstance(left, ast.Constant) and left.value == "ClothPatternWorkbench"
            for left in [node.left, *node.comparators]
        )
    ]
    assert tests_for_absence


def test_blanket_harness_registers_before_first_workbench_use():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    functions = _functions(tree)

    main_calls = _called_names(functions["main"])
    assert main_calls.index("_ensure_workbench_registration") < main_calls.index("_load_cloth_modules")

    adopt_calls = _called_names(functions["adopt_sketch"])
    assert adopt_calls.index("_require_workbench_registration") < adopt_calls.index(
        "create_pattern_piece_from_selected_sketch"
    )
