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
else
  bash tools/ci/resolve_guarded_rebase_conflicts.sh
fi
