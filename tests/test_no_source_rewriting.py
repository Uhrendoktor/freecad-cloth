"""Regression tests for the repository source-rewriting policy."""

from tools.ci.check_no_source_rewriting import (
    python_source_rewrite_violations,
    workflow_source_rewrite_violations,
)


def test_loaded_python_source_cannot_be_rewritten_before_execution() -> None:
    source = """
from pathlib import Path
source_path = Path("fixture.py")
source = source_path.read_text(encoding="utf-8")
source = source.replace("old_function()", "new_function()")
exec(compile(source, str(source_path), "exec"))
"""
    violations = python_source_rewrite_violations(source, "bad_fixture.py")
    assert len(violations) == 1
    assert "do not transform loaded Python source" in violations[0]


def test_read_modify_write_of_python_source_is_rejected() -> None:
    source = """
from pathlib import Path
path = Path("tools/validator.py")
source = path.read_text(encoding="utf-8")
path.write_text(source.replace("old", "new"), encoding="utf-8")
"""
    violations = python_source_rewrite_violations(source, "bad_editor.py")
    assert any("do not transform loaded Python source" in item for item in violations)


def test_ordinary_string_normalization_is_allowed() -> None:
    source = """
def normalize(value: str) -> str:
    return value.replace(",", " ").strip()
"""
    assert python_source_rewrite_violations(source) == ()


def test_configuration_text_used_as_test_data_is_allowed() -> None:
    source = """
from pathlib import Path
workflow = Path(".github/workflows/canonical-execution.yml").read_text()
tampered = workflow.replace("required command", "")
assert tampered
"""
    assert python_source_rewrite_violations(source) == ()


def test_inline_tracked_source_patch_in_workflow_is_rejected() -> None:
    workflow = """
run: |
  python -c 'from pathlib import Path;p=Path("tools/ci/checks.py");s=p.read_text();p.write_text(s.replace("old", "new"))'
"""
    violations = workflow_source_rewrite_violations(workflow, "workflow.yml")
    assert violations
    assert "edits tracked source/configuration" in violations[0]


def test_inline_json_inventory_repair_in_workflow_is_rejected() -> None:
    workflow = """
run: |
  python -c 'import pathlib;p=pathlib.Path("pyrightconfig.json");p.write_text("{}")'
"""
    assert workflow_source_rewrite_violations(workflow, "workflow.yml")


def test_multiline_shell_script_cannot_patch_tracked_python_source() -> None:
    workflow = """name: example
jobs:
  edit:
    steps:
      - run: |
          python - <<'PY'
          from pathlib import Path
          path = Path("tools/ci/checks.py")
          source = path.read_text()
          path.write_text(source.replace("old", "new"))
          PY
"""
    violations = workflow_source_rewrite_violations(workflow, "workflow.yml")
    assert violations
    assert "edits tracked source/configuration" in violations[0]


def test_git_checkout_must_not_restore_a_workflow_as_conflict_repair() -> None:
    workflow = """name: example
jobs:
  edit:
    steps:
      - run: |
          git checkout origin/main -- .github/workflows/canonical-execution.yml
"""
    assert workflow_source_rewrite_violations(workflow, "workflow.yml")


def test_regex_substitution_of_loaded_source_is_rejected() -> None:
    source = """
from pathlib import Path
import re
path = Path("tools/ci/checks.py")
source = path.read_text(encoding="utf-8")
patched = re.sub("old", "new", source)
"""
    violations = python_source_rewrite_violations(source, "bad_regex_editor.py")
    assert any("do not transform loaded Python source" in item for item in violations)


def test_normal_workflow_python_command_is_allowed() -> None:
    workflow = """
run: |
  python tools/ci/validate_ci_structure.py
  python -m pytest -q tests
"""
    assert workflow_source_rewrite_violations(workflow) == ()
