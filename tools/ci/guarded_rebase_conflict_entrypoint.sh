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
    # The obsolete snapshot may include the duplicate tail; only the kept mainline resolver must parse.
    ! git show "origin/main:${resolver_path}" | bash -n ||
    ! git diff --unified=0 "${rebase_commit}^" "${rebase_commit}" -- "${resolver_path}" | grep -Fq "tests/test_build_visual_gifs.py" ||
    ! git diff --unified=0 "${rebase_commit}^" "${rebase_commit}" -- "${resolver_path}" | grep -Fq "9a43f60fabacfcd894a560d58b10ed6bdd2533e6" ||
    git diff --unified=0 "${rebase_commit}^" "${rebase_commit}" -- "${resolver_path}" | grep -Eq '^\+[^+]'; then
    echo "::error::Refusing resolver cleanup replay outside the exact deletion-only 188f4ce commit and verified mainline resolver."
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
      bash tools/ci/guarded_rebase_conflict_entrypoint.sh
    else
      exit 1
    fi
  fi
elif [[ "${rebase_commit}" == "cf3c1277814794e364ca1548ad47b1b3673e0f2c" ]] &&
  [[ "${conflicted_files}" == "tools/ci/resolve_guarded_rebase_conflicts.sh" ]]; then
  resolver_path="tools/ci/resolve_guarded_rebase_conflicts.sh"
  test_path="tests/test_runner_routing_contract.py"
  expected_paths="$(printf '%s\n' "${test_path}" "${resolver_path}" | LC_ALL=C sort)"
  changed_paths="$(git diff-tree --no-commit-id --name-only -r "${rebase_commit}" | LC_ALL=C sort)"
  if [[ "${changed_paths}" != "${expected_paths}" ]] ||
    ! git show "origin/main:${resolver_path}" | bash -n ||
    ! git show "${rebase_commit}:${resolver_path}" | grep -Fq "9a43f60fabacfcd894a560d58b10ed6bdd2533e6" ||
    ! git show "${rebase_commit}:${resolver_path}" | grep -Fq "Preserving mainline GIF command-runner API and stronger regression test" ||
    ! git show "origin/main:${resolver_path}" | grep -Fq "9a43f60fabacfcd894a560d58b10ed6bdd2533e6" ||
    ! git show "origin/main:${resolver_path}" | grep -Fq "a59f58d25537de846677f89a7858562cfcfc9672" ||
    ! git show "origin/main:${resolver_path}" | grep -Fq "f7cc118eb4aafafbaf1e5bcc7526140ad2e6f28e" ||
    ! git show "origin/main:${resolver_path}" | grep -Fq "bbd581e2df7ed83509755ef7a32850edd3441f49" ||
    ! git show "origin/main:${resolver_path}" | grep -Fq "99b9aa0e93e1a5e071a989c9b0a751dc2d8d6bbd" ||
    ! git show "origin/main:${resolver_path}" | grep -Fq "69999107b2e8888a5d179835b8297b21fef19d74"; then
    echo "::error::Refusing resolver restoration replay outside the exact cf3c1277 two-file commit and verified current-main resolver."
    exit 1
  fi
  for marker in \
    "syntax_check.returncode == 0" \
    "Strict checks and guarded safe Ruff batch" \
    "run_safe_ruff_batch.sh" \
    "[apply-safe-ruff]" \
    "Preserving mainline GIF command-runner API and stronger regression test" \
    "jobs: list[Future[None]] = []" \
    "from concurrent.futures import Future, ThreadPoolExecutor, as_completed" \
    "options=CommandOptions(check=True, timeout=timeout)" \
    "Preserving the already-typed combo-box protocol and applying only the exact a59f docstring." \
    "Applying exact structural seam/document and string-valued combo protocols across the post-Ruff import layout" \
    "Normalizing the already-typed topology GUI to the exact Ruff output"; do
    if ! git show "${rebase_commit}:${test_path}" | grep -Fq "${marker}" ||
      ! git show "origin/main:${test_path}" | grep -Fq "${marker}"; then
      echo "::error::Current-main contract coverage does not supersede the exact cf3c1277 test addition: ${marker}"
      exit 1
    fi
  done
  echo "::notice::Skipping exact cf3c1277 resolver restoration; current main already contains the restored handlers and equivalent contract coverage."
  git checkout --ours -- "${resolver_path}"
  git checkout origin/main -- "${test_path}"
  git add "${resolver_path}" "${test_path}"
  if ! git rebase --skip; then
    rebase_merge="$(git rev-parse --git-path rebase-merge)"
    rebase_apply="$(git rev-parse --git-path rebase-apply)"
    if [[ -d "${rebase_merge}" || -d "${rebase_apply}" ]]; then
      bash tools/ci/guarded_rebase_conflict_entrypoint.sh
    else
      exit 1
    fi
  fi
else
  bash tools/ci/resolve_guarded_rebase_conflicts.sh
fi
