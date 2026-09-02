"""Focused regression checks for native Cloth workbench registration.

These tests intentionally inspect the registration declarations rather than
requiring a running FreeCAD GUI. The public registration contract is the
stable bridge between the three workbenches and FreeCAD's native menus and
commands.
"""
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SEWING_GROUPS = [
    (
        "Sewing Creation",
        [
            "ClothSewing_CreateSeam",
            "ClothSewing_CreateMNSewing",
            "ClothSewing_CreateNetwork",
            "ClothSewing_FreeSewing",
        ],
    ),
    (
        "Sewing Editing",
        [
            "ClothSewing_CreateOperation",
            "ClothSewing_EditOperation",
            "ClothSewing_EditNetwork",
            "ClothSewing_ReverseSeam",
            "ClothSewing_ToggleAlignment",
        ],
    ),
    (
        "Validation & View",
        [
            "ClothSewing_Validate",
            "ClothSewing_RepairSeam",
            "ClothSewing_Show2D",
        ],
    ),
    ("Fitting & Avatar", "FROM_MODULES"),
]
EXPECTED_SEWING_TOOLBAR = [
    "ClothSewing_CreateSeam",
    "ClothSewing_CreateOperation",
    "ClothSewing_Validate",
]


def _parse_initgui():
    """Parse InitGui.py or fall back to package workbench source."""
    initgui = ROOT / "InitGui.py"
    if initgui.exists():
        tree = ast.parse(initgui.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == "ClothSewingWorkbench":
                return tree
        # Fall back to package source if class not found at root
        workbench = ROOT / "freecad_cloth" / "sewing" / "workbench.py"
        if workbench.exists():
            return ast.parse(workbench.read_text(encoding="utf-8"))
    else:
        # InitGui.py doesn't exist, try package source directly
        workbench = ROOT / "freecad_cloth" / "sewing" / "workbench.py"
        if workbench.exists():
            return ast.parse(workbench.read_text(encoding="utf-8"))
    raise FileNotFoundError("InitGui.py or freecad_cloth/sewing/workbench.py not found")


def _class(tree, name):
    return next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == name
    )


def _literal_commands(module_name):
    """Resolve module_name to a package path and return COMMANDS set."""
    _PATH_MAP = {
        "PatternCommands": "freecad_cloth/pattern/PatternCommands",
        "SewingCommands": "freecad_cloth/sewing/SewingCommands",
        "SewingNetworkCommands": "freecad_cloth/sewing/SewingNetworkCommands",
        "FittingCommands": "freecad_cloth/simulation/FittingCommands",
        "AvatarCommands": "freecad_cloth/avatar/AvatarCommands",
        "SimulationCommands": "freecad_cloth/simulation/SimulationCommands",
    }
    pkg = _PATH_MAP.get(module_name, module_name)
    tree = ast.parse((ROOT / f"{pkg}.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "COMMANDS"
            for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            assert isinstance(value, list), f"{module_name}.COMMANDS must be a list"
            return set(value)
    raise AssertionError(f"{module_name}.COMMANDS is missing")


def _literal_constant(tree, name):
    """Resolve a constant from InitGui.py source or runtime."""
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        ):
            return ast.literal_eval(node.value)
    # Fallback: read from runtime namespace
    import InitGui
    val = getattr(InitGui, name, None)
    if val is not None:
        return set(val)
    raise AssertionError(f"InitGui.py is missing {name}")


def _initialize_method(tree, class_name):
    workbench = _class(tree, class_name)
    return next(
        node for node in workbench.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "Initialize"
    )


def _module_command_union(expr):
    """Resolve a simple ``A.COMMANDS + B.COMMANDS`` AST expression."""
    assert isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Add)
    modules = []
    for operand in (expr.left, expr.right):
        assert isinstance(operand, ast.Attribute)
        assert operand.attr == "COMMANDS"
        assert isinstance(operand.value, ast.Name)
        modules.append(operand.value.id)
    return set().union(*(_literal_commands(module) for module in modules))


def test_sewing_menu_groups_have_stable_names_order_and_complete_commands():
    tree = _parse_initgui()
    groups = _literal_constant(tree, "SEWING_COMMAND_GROUPS")
    assert groups == tuple(
        (name, tuple(commands))
        for name, commands in EXPECTED_SEWING_GROUPS[:-1]
    )

    sewing_commands = (
        _literal_commands("SewingCommands")
        | _literal_commands("SewingNetworkCommands")
    )
    grouped = set(command for _name, commands in groups for command in commands)
    assert grouped == sewing_commands
    assert grouped.isdisjoint(
        _literal_commands("FittingCommands") | _literal_commands("AvatarCommands")
    )


def test_fitting_and_avatar_form_the_final_sewing_menu_group():
    tree = _parse_initgui()
    initialize = _initialize_method(tree, "ClothSewingWorkbench")
    group_append = next(
        node for node in ast.walk(initialize)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "append"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Tuple)
    )
    group_name = ast.literal_eval(group_append.args[0].elts[0])
    group_commands = _module_command_union(group_append.args[0].elts[1])
    assert group_name == "Fitting & Avatar"
    assert group_commands == _literal_commands("FittingCommands") | _literal_commands("AvatarCommands")


def test_sewing_toolbar_is_stable_and_subset_of_registered_commands():
    tree = _parse_initgui()
    toolbar = _literal_constant(tree, "SEWING_TOOLBAR_COMMANDS")
    assert set(toolbar) == set(EXPECTED_SEWING_TOOLBAR), f"Expected {EXPECTED_SEWING_TOOLBAR}, got {toolbar}"
    assert len(toolbar) == len(set(toolbar))

    all_commands = (
        _literal_commands("SewingCommands")
        | _literal_commands("SewingNetworkCommands")
        | _literal_commands("FittingCommands")
        | _literal_commands("AvatarCommands")
    )
    assert set(toolbar) <= all_commands


def test_sewing_registration_passes_group_and_toolbar_constants_to_freecad():
    tree = _parse_initgui()
    initialize = _initialize_method(tree, "ClothSewingWorkbench")
    calls = [
        node for node in ast.walk(initialize)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "_register_groups"
    ]
    assert len(calls) == 1
    call = calls[0]
    assert isinstance(call.args[0], ast.Name)
    assert call.args[0].id == "groups"
    keywords = {keyword.arg: keyword.value for keyword in call.keywords}
    assert isinstance(keywords["toolbar_name"], ast.Attribute)
    assert keywords["toolbar_name"].attr == "MenuText"
    assert isinstance(keywords["toolbar_commands"], ast.Name)
    assert keywords["toolbar_commands"].id == "SEWING_TOOLBAR_COMMANDS"


def test_sewing_workbench_covers_all_command_modules_without_private_registration_lists():
    tree = _parse_initgui()
    initialize = _initialize_method(tree, "ClothSewingWorkbench")
    modules = {
        node.value.id
        for node in ast.walk(initialize)
        if isinstance(node, ast.Attribute)
        and node.attr == "COMMANDS"
        and isinstance(node.value, ast.Name)
    }
    assert modules == {
        "SewingCommands",
        "SewingNetworkCommands",
        "FittingCommands",
        "AvatarCommands",
    }


def test_workbench_command_groups_do_not_overlap():
    groups = {
        "Pattern": _literal_commands("PatternCommands") | _literal_commands("PatternMarks"),
        "Sewing": (
            _literal_commands("SewingCommands")
            | _literal_commands("SewingNetworkCommands")
            | _literal_commands("FittingCommands")
            | _literal_commands("AvatarCommands")
        ),
        "Simulation": _literal_commands("SimulationCommands") | _literal_commands("DrapeCommands"),
    }

    names = {}
    for workbench, commands in groups.items():
        assert commands, f"{workbench} workbench has no commands"
        for command in commands:
            previous = names.setdefault(command, workbench)
            assert previous == workbench, (
                f"command {command!r} is registered by both "
                f"{previous} and {workbench}"
            )
