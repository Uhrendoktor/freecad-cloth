"""Regression tests for the repository-wide source-rewriting policy."""

from __future__ import annotations

from tools.ci.check_no_source_rewriting import (
    python_source_rewrite_violations,
    workflow_source_rewrite_violations,
)


def test_python_source_rewriting_and_dynamic_execution_are_rejected() -> None:
    """A Python file must not be read, patched, compiled, and executed as a string."""
    sample = """
from pathlib import Path

source_path = Path("fixture.py")
source = source_path.read_text(encoding="utf-8")
source = source.replace("old_expression", "new_expression")
exec(compile(source, str(source_path), "exec"))
"""
    violations = python_source_rewrite_violations(sample, "fixture.py")
    assert any("must not be rewritten" in issue for issue in violations)
    assert any(
        "transformed source must not be executed dynamically" in issue for issue in violations
    )
    assert any("transformed source must not be compiled" in issue for issue in violations)


def test_generated_python_source_cannot_be_compiled() -> None:
    """Generated executable code is prohibited even if it is not read from a file."""
    sample = 'generated = "def patched():\\n    return 1\\n"\ncompile(generated, "<generated>", "exec")\n'
    violations = python_source_rewrite_violations(sample, "generator.py")
    assert any("compiling generated Python source" in issue for issue in violations)


def test_inline_generated_python_source_cannot_be_compiled() -> None:
    """Literal source code passed straight to compile is prohibited too."""
    sample = 'compile("def generated():\\n    return 1", "<generated>", "exec")\n'
    violations = python_source_rewrite_violations(sample, "inline_generator.py")
    assert any("compiling generated Python source" in issue for issue in violations)


def test_regular_expression_replacement_of_python_source_is_rejected() -> None:
    """Regex substitutions are also source rewriting when applied to Python file contents."""
    sample = """
from pathlib import Path
import re

source_path = Path("fixture.py")
source = source_path.read_text(encoding="utf-8")
patched = re.sub("old_expression", "new_expression", source)
compile(patched, str(source_path), "exec")
"""
    violations = python_source_rewrite_violations(sample, "regex_generator.py")
    assert any("must not be rewritten" in issue for issue in violations)
    assert any("transformed source must not be compiled" in issue for issue in violations)


def test_checked_in_bootstrap_source_can_be_executed_without_modification() -> None:
    """FreeCAD's host bootstrap may execute a checked-in file when it was not rewritten."""
    sample = """
from pathlib import Path

init_gui = Path("InitGui.py")
exec(compile(init_gui.read_text(encoding="utf-8"), str(init_gui), "exec"))
"""
    assert python_source_rewrite_violations(sample, "bootstrap.py") == ()


def test_checked_in_bootstrap_source_can_be_read_from_open_context() -> None:
    """Support FreeCAD bootstrap scripts that use open(...).read() in a with block."""
    sample = """
import os

init_gui = os.path.join(ROOT, "InitGui.py")
with open(init_gui, encoding="utf-8") as handle:
    exec(compile(handle.read(), init_gui, "exec"), globals(), globals())
"""
    assert python_source_rewrite_violations(sample, "bootstrap.py") == ()


def test_read_only_syntax_check_of_checked_in_python_is_allowed() -> None:
    """Compiling unmodified source-file text for syntax validation is legitimate."""
    sample = """
from pathlib import Path

source_path = Path("fixture.py")
source = source_path.read_text(encoding="utf-8")
compile(source, str(source_path), "exec")
"""
    assert python_source_rewrite_violations(sample, "syntax_check.py") == ()


def test_ordinary_string_normalization_is_allowed() -> None:
    """String replacements used for data normalization are not source rewriting."""
    sample = 'label = command_name.replace("_", " ").title()\n'
    assert python_source_rewrite_violations(sample, "labels.py") == ()


def test_inline_workflow_file_mutations_are_rejected() -> None:
    """Inline Python and in-place shell edits must be ordinary reviewed changes."""
    workflow = """
- run: python -c 'from pathlib import Path; p=Path("config.py"); s=p.read_text(); p.write_text(s.replace("old", "new"))'
- run: sed -i 's/old/new/' config.py
"""
    violations = workflow_source_rewrite_violations(workflow, "workflow.yml")
    assert len(violations) == 2
    assert all("prohibited" in issue for issue in violations)


def test_non_mutating_workflow_commands_are_allowed() -> None:
    """Ordinary shell inspection and Python invocations remain permitted."""
    workflow = """
- run: python -c 'print("validation")'
- run: sed -n '1,20p' README.md
"""
    assert workflow_source_rewrite_violations(workflow, "workflow.yml") == ()
