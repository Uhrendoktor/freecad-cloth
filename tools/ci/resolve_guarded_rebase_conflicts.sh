#!/usr/bin/env bash
# Copyright (C) 2026 FreeCAD Cloth contributors
set -euo pipefail

rebase_merge="$(git rev-parse --git-path rebase-merge)"
rebase_apply="$(git rev-parse --git-path rebase-apply)"

while [[ -d "$rebase_merge" || -d "$rebase_apply" ]]; do
  conflicts="$(git diff --name-only --diff-filter=U)"
  if [[ "$conflicts" == ".agent/PLANS.md" ]]; then
    echo "::warning::Retaining main's non-runtime .agent/PLANS.md."
    git checkout --ours -- .agent/PLANS.md
    git add .agent/PLANS.md
    if ! GIT_EDITOR=true git rebase --continue; then
      [[ -d "$rebase_merge" || -d "$rebase_apply" ]] || exit 1
    fi
  elif [[ "$conflicts" == "tools/ci/python_validation.py" ]]; then
    rebase_commit="$(git rev-parse REBASE_HEAD)"
    if [[ "$rebase_commit" != "fb53561e133e531d418a61d35620c8bf9fe31ceb" ]] ||
      ! git show origin/main:tools/ci/python_validation.py | grep -Fq "tests/test_diagnostics_gui_contract.py" ||
      ! git show origin/main:tools/ci/python_validation.py | grep -Fq "tests/test_fitting_gui_status.py"; then
      echo "::error::Refusing to skip a Python test-routing conflict not proven redundant."
      exit 1
    fi
    echo "::warning::Skipping the exact GUI-routing commit because both added modules are already routed on main."
    if ! GIT_EDITOR=true git rebase --skip; then
      [[ -d "$rebase_merge" || -d "$rebase_apply" ]] || exit 1
    fi
  elif [[ "$conflicts" == "pyrightconfig.json" ]]; then
    rebase_commit="$(git rev-parse REBASE_HEAD)"
    if [[ "$rebase_commit" != "0f8ae7645c3c2fe6491dfe9b93477d28f047563b" ]] ||
      ! git show origin/main:pyrightconfig.json | grep -Fq '"typeCheckingMode": "standard"' ||
      ! git show origin/main:pyrightconfig.json | grep -Fq '"reportMissingImports": "none"' ||
      ! git show "${rebase_commit}:pyrightconfig.json" | grep -Fq '"typeCheckingMode": "strict"' ||
      ! git show "${rebase_commit}:pyrightconfig.json" | grep -Fq '    "."' ||
      git show "${rebase_commit}:pyrightconfig.json" | grep -Fq '"exclude":'; then
      echo "::error::Refusing a Pyright config conflict outside the verified repository-wide strict-profile commit."
      exit 1
    fi
    echo "::warning::Taking the exact repository-wide strict Pyright profile while replaying its original expansion commit."
    git checkout --theirs -- pyrightconfig.json
    git add pyrightconfig.json
    if ! GIT_EDITOR=true git rebase --continue; then
      [[ -d "$rebase_merge" || -d "$rebase_apply" ]] || exit 1
    fi
  elif [[ "$conflicts" == "tools/ci/validate_ci_structure.py" ]]; then
    rebase_commit="$(git rev-parse REBASE_HEAD)"
    if [[ "$rebase_commit" != "0e5acdf6bf06f40babe20a3b8afac1ac455c92be" ]] ||
      ! git show origin/main:tools/ci/validate_ci_structure.py | grep -Fq 'ROOT / "tools/ci/pbd_constraint_group_profile.py",' ||
      ! git show "${rebase_commit}:tools/ci/validate_ci_structure.py" | grep -Fq 'PYRIGHT_EXPECTED_INCLUDE = (".",)' ||
      ! git show "${rebase_commit}:tools/ci/validate_ci_structure.py" | grep -Fq 'config.get("typeCheckingMode") != "strict"'; then
      echo "::error::Refusing a CI-structure conflict outside the verified strict-Pyright migration commit and current-main PBD helper contract."
      exit 1
    fi
    echo "::warning::Preserving main's PBD diagnostic helper and transplanting only the exact strict-Pyright policy changes."
    git checkout --ours -- tools/ci/validate_ci_structure.py
    python3 - <<'PY'
from pathlib import Path

path = Path("tools/ci/validate_ci_structure.py")
source = path.read_text(encoding="utf-8")
start_marker = "# Stage semantic type checking deliberately:"
end_marker = "QUALITY_RUNNER_COMMANDS = "
if source.count(start_marker) != 1 or source.count(end_marker) != 1:
    raise SystemExit("Unexpected Pyright inventory structure; refusing manual transplant.")
start = source.index(start_marker)
end = source.index(end_marker, start)
strict_profile = (
    "# One strict Pyright profile covers the repository root; new tracked modules need no opt-in.\n"
    'PYRIGHT_EXPECTED_INCLUDE = (".",)\n'
    "PYRIGHT_EXPECTED_EXCLUDE: tuple[str, ...] = ()\n"
    "PYRIGHT_EXPECTED_STRICT: tuple[str, ...] = ()\n\n"
)
source = source[:start] + strict_profile + source[end:]

replacements = {
    '"""Require the reviewed staged Pyright inventory and prevent accidental scope drift.':
        '"""Require strict Pyright analysis to cover the repository\'s complete Python tree.',
    'added_modules: New production modules to check against the selected inventory.':
        'added_modules: New production modules to check against the repository-wide scope.',
    'Returns:\n        Contract violations describing changes to the reviewed scope or uncovered modules.':
        'Returns:\n        Contract violations describing any narrowed scope or disabled diagnostics.',
    '<Pyright include scope differs from the reviewed inventory>':
        '<Pyright include scope must cover the entire repository root>',
    '<Pyright exclude scope differs from the reviewed inventory>':
        '<Pyright must not exclude repository source paths>',
    '<Pyright strict scope differs from the reviewed simulation core>':
        '<Pyright strict mode must apply globally, not through a path subset>',
    'if config.get("typeCheckingMode") != "standard":\n        violations.append("<Pyright default mode must remain standard outside the strict core>")':
        'if config.get("typeCheckingMode") != "strict":\n        violations.append("<Pyright typeCheckingMode must be strict>")',
    'if config.get("reportMissingImports", "none") != "none":\n        violations.append("<Pyright missing-import policy differs from the reviewed host boundary>")':
        'if config.get("reportMissingImports", "error") != "error":\n        violations.append("<Pyright missing-import diagnostics must be blocking>")',
    'if config.get("reportMissingModuleSource", "none") != "none":\n        violations.append(\n            "<Pyright missing-module-source policy differs from the reviewed host boundary>"\n        )':
        'if config.get("reportMissingModuleSource", "error") != "error":\n        violations.append("<Pyright missing-module-source diagnostics must be blocking>")',
    '<new Python module is outside Pyright include/exclude scope: {path}>':
        '<new Python module is outside strict Pyright coverage: {path}>',
    '"""Require the curated ty core profile to fail on warning-level diagnostics.':
        '"""Require every ty diagnostic to be blocking for the complete tracked Python inventory.',
}
for old, new in replacements.items():
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"Expected exactly one occurrence for transplant anchor; found {count}: {old[:90]}")
    source = source.replace(old, new)
if 'ROOT / "tools/ci/pbd_constraint_group_profile.py",' not in source:
    raise SystemExit("Mainline PBD diagnostic helper requirement was not preserved.")
if 'PYRIGHT_EXPECTED_INCLUDE = (".",)' not in source or '"typeCheckingMode") != "strict"' not in source:
    raise SystemExit("Strict Pyright profile transplant is incomplete.")
path.write_text(source, encoding="utf-8")
PY
    git add tools/ci/validate_ci_structure.py
    if ! GIT_EDITOR=true git rebase --continue; then
      [[ -d "$rebase_merge" || -d "$rebase_apply" ]] || exit 1
    fi
  elif [[ "$conflicts" == "docs/developers/UI_STYLE_GUIDE.md" ]]; then
    rebase_commit="$(git rev-parse REBASE_HEAD)"
    if [[ "$rebase_commit" != "67d656007deea6692d332e0954cb8aa1f99e92e6" ]] ||
      ! git show origin/main:docs/developers/UI_STYLE_GUIDE.md | grep -Fq 'make_scroll_area(content, QtWidgets)' ||
      ! git show origin/main:docs/developers/UI_STYLE_GUIDE.md | grep -Fq 'configure_form_layout(layout, QtWidgets)' ||
      ! git show origin/main:docs/developers/UI_STYLE_GUIDE.md | grep -Fq 'make_disclosure(title, content, QtCore, QtWidgets, expanded=False)' ||
      ! git show "${rebase_commit}:docs/developers/UI_STYLE_GUIDE.md" | grep -Fq 'make_disclosure(title, content, QtCore, QtWidgets, *, expanded=False)'; then
      echo "::error::Refusing a UI guide conflict outside the verified keyword-only disclosure documentation commit and mainline helper additions."
      exit 1
    fi
    echo "::warning::Preserving mainline UI guidance and applying only the verified keyword-only disclosure signature."
    git checkout --ours -- docs/developers/UI_STYLE_GUIDE.md
    python3 - <<'PY'
from pathlib import Path

path = Path("docs/developers/UI_STYLE_GUIDE.md")
source = path.read_text(encoding="utf-8")
old = "- make_disclosure(title, content, QtCore, QtWidgets, expanded=False) uses a checkable Qt tool button to hide/show a settings container while preserving contained widgets and values."
new = "- make_disclosure(title, content, QtCore, QtWidgets, *, expanded=False) uses a checkable Qt tool button to hide/show a settings container while preserving contained widgets and values."
if source.count(old) != 1:
    raise SystemExit("Expected exactly one old disclosure signature; refusing documentation transplant.")
if source.count("make_scroll_area(content, QtWidgets)") != 1:
    raise SystemExit("Mainline scroll-area guidance is missing or duplicated.")
if source.count("configure_form_layout(layout, QtWidgets)") != 1:
    raise SystemExit("Mainline form-layout guidance is missing or duplicated.")
source = source.replace(old, new)
path.write_text(source, encoding="utf-8")
PY
    git add docs/developers/UI_STYLE_GUIDE.md
    if ! GIT_EDITOR=true git rebase --continue; then
      [[ -d "$rebase_merge" || -d "$rebase_apply" ]] || exit 1
    fi
  else
    echo "::error::Unsupported rebase conflict; refusing automatic resolution: ${conflicts:-(none)}"
    exit 1
  fi
done
