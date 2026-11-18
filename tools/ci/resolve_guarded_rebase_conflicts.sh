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
  else
    echo "::error::Unsupported rebase conflict; refusing automatic resolution: ${conflicts:-(none)}"
    exit 1
  fi
done
