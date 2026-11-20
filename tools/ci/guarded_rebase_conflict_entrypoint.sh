#!/usr/bin/env bash
# Resolve the one historical rebase commit superseded by the full mainline resolver.
set -euo pipefail

rebase_commit="$(git rev-parse REBASE_HEAD)"
conflicted_files="$(git diff --name-only --diff-filter=U)"

if [[ "${rebase_commit}" == "ec93982d0267fe54c679e3edb89e67f42dff09ec" ]] &&
  [[ "${conflicted_files}" == "tools/ci/resolve_guarded_rebase_conflicts.sh" ]]; then
  echo "::notice::Skipping the exact historical resolver-truncation commit; current main already carries the complete resolver."
  git checkout --ours -- tools/ci/resolve_guarded_rebase_conflicts.sh
  git add tools/ci/resolve_guarded_rebase_conflicts.sh
  if ! git rebase --skip; then
    rebase_merge="$(git rev-parse --git-path rebase-merge)"
    rebase_apply="$(git rev-parse --git-path rebase-apply)"
    if [[ -d "${rebase_merge}" || -d "${rebase_apply}" ]]; then
      bash tools/ci/resolve_guarded_rebase_conflicts.sh
    else
      exit 1
    fi
  fi
elif [[ "${rebase_commit}" == "188f4ce80b19b47679d616ede5235f67bc2d38a2" ]] &&
  [[ "${conflicted_files}" == "tools/ci/resolve_guarded_rebase_conflicts.sh" ]]; then
  resolver_path="tools/ci/resolve_guarded_rebase_conflicts.sh"
  if [[ "$(git diff-tree --no-commit-id --name-only -r "${rebase_commit}")" != "${resolver_path}" ]] ||
    ! git show "${rebase_commit}:${resolver_path}" | bash -n ||
    ! git show "origin/main:${resolver_path}" | bash -n ||
    ! git diff --unified=0 "${rebase_commit}^" "${rebase_commit}" -- "${resolver_path}" | grep -Fq "tests/test_build_visual_gifs.py" ||
    ! git diff --unified=0 "${rebase_commit}^" "${rebase_commit}" -- "${resolver_path}" | grep -Fq "9a43f60fabacfcd894a560d58b10ed6bdd2533e6" ||
    git diff --unified=0 "${rebase_commit}^" "${rebase_commit}" -- "${resolver_path}" | grep -Eq '^\+[^+]'; then
    echo "::error::Refusing resolver cleanup replay outside the exact deletion-only 188f4ce commit and valid resolver states."
    exit 1
  fi
  for marker in \
    "9a43f60fabacfcd894a560d58b10ed6bdd2533e6" \
    "69999107b2e8888a5d179835b8297b21fef19d74"; do
    if ! git show "origin/main:${resolver_path}" | grep -Fq "${marker}"; then
      echo "::error::Current-main resolver is missing required exact conflict case: ${marker}"
      exit 1
    fi
  done
  echo "::notice::Skipping the exact deletion-only duplicate-tail cleanup; validated current main already contains the complete resolver."
  git checkout --ours -- "${resolver_path}"
  git add "${resolver_path}"
  if ! git rebase --skip; then
    rebase_merge="$(git rev-parse --git-path rebase-merge)"
    rebase_apply="$(git rev-parse --git-path rebase-apply)"
    if [[ -d "${rebase_merge}" || -d "${rebase_apply}" ]]; then
      bash tools/ci/resolve_guarded_rebase_conflicts.sh
    else
      exit 1
    fi
  fi
else
  bash tools/ci/resolve_guarded_rebase_conflicts.sh
fi
