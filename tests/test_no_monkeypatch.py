# Copyright (C) 2026 FreeCAD Cloth contributors
"""Repository contract preventing regression to monkeypatch-based tests."""

from tools.ci.check_no_monkeypatch import (
    python_monkeypatch_violations,
    repository_violations,
)


def test_pytest_monkeypatch_fixtures_are_rejected() -> None:
    source = """
def test_behavior(monkeypatch):
    monkeypatch.setattr(target, "value", replacement)
"""
    violations = python_monkeypatch_violations(source, "tests/fixture.py")
    assert any("monkeypatch fixtures are forbidden" in item for item in violations)


def test_unittest_patch_imports_are_rejected() -> None:
    source = "from unittest.mock import patch\n\nwith patch.dict('sys.modules', {}):\n    pass\n"
    violations = python_monkeypatch_violations(source, "tests/fixture.py")
    assert any("unittest.mock patching is forbidden" in item for item in violations)


def test_sys_modules_mutations_are_rejected_but_reads_are_allowed() -> None:
    read_source = "old = sys.modules.get('FreeCAD')\n"
    assert python_monkeypatch_violations(read_source, "tests/inspect_module.py") == ()
    violations = python_monkeypatch_violations(
        "sys.modules['FreeCAD'] = fake_module\n", "tests/fixture.py"
    )
    assert any("sys.modules mutation is forbidden" in item for item in violations)


def test_imported_module_attribute_replacement_is_rejected() -> None:
    source = "import freecad_cloth.gui as gui_module\ngui_module.Gui = fake_gui\n"
    violations = python_monkeypatch_violations(source, "tests/fixture.py")
    assert any("replacing an imported module attribute is forbidden" in item for item in violations)


def test_explicit_dependency_injection_is_allowed() -> None:
    source = """
def build_panel(*, gui, assign_target):
    return gui, assign_target
"""
    assert python_monkeypatch_violations(source, "tests/injected.py") == ()


def test_repository_has_no_monkeypatching() -> None:
    violations = repository_violations()
    assert violations == ()
