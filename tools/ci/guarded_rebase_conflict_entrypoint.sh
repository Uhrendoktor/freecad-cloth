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
elif [[ "${rebase_commit}" == "aca0d1ae82001b0c74347d106c08cf45bcb4ea8a" ]]; then
  resolver_path="tools/ci/resolve_guarded_rebase_conflicts.sh"
  test_path="tests/test_runner_routing_contract.py"
  expected_paths="$(printf '%s\n' "${test_path}" "${resolver_path}" | LC_ALL=C sort)"
  expected_conflicts="$(printf '%s\n' "${test_path}" "${resolver_path}" | LC_ALL=C sort)"
  changed_paths="$(git diff-tree --no-commit-id --name-only -r "${rebase_commit}" | LC_ALL=C sort)"
  if [[ "${changed_paths}" != "${expected_paths}" ]] ||
    { [[ "${conflicted_files}" != "${resolver_path}" ]] &&
      [[ "${conflicted_files}" != "${test_path}" ]] &&
      [[ "${conflicted_files}" != "${expected_conflicts}" ]]; } ||
    ! git show "origin/main:${resolver_path}" | bash -n ||
    ! git show "origin/main:${resolver_path}" | grep -Fq "9a43f60fabacfcd894a560d58b10ed6bdd2533e6" ||
    ! git show "${rebase_commit}:${resolver_path}" | grep -Fq "9a43f60fabacfcd894a560d58b10ed6bdd2533e6" ||
    ! git show "origin/main:${test_path}" | grep -Fq "9a43f60fabacfcd894a560d58b10ed6bdd2533e6" ||
    ! git show "${rebase_commit}:${test_path}" | grep -Fq "9a43f60fabacfcd894a560d58b10ed6bdd2533e6"; then
    echo "::error::Refusing GIF resolver clause repair outside the exact aca0d1ae two-file commit and verified current-main copies."
    exit 1
  fi
  echo "::notice::Skipping exact aca0d1ae resolver clause restoration; current main already has the valid GIF handler and corrected contract assertion."
  git checkout origin/main -- "${resolver_path}" "${test_path}"
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
elif [[ "${rebase_commit}" == "97b837b940384a9279af1884d44014bd8a89d453" ]] &&
  [[ "${conflicted_files}" == "tests/test_runner_routing_contract.py" ]]; then
  test_path="tests/test_runner_routing_contract.py"
  changed_paths="$(git diff-tree --no-commit-id --name-only -r "${rebase_commit}")"
  if [[ "${changed_paths}" != "${test_path}" ]] ||
    git diff --unified=0 "${rebase_commit}^" "${rebase_commit}" -- "${test_path}" | grep -Eq '^\+[^+]' ||
    ! git show "origin/main:${test_path}" | grep -Fq "syntax_check.returncode == 0" ||
    ! git show "origin/main:${test_path}" | grep -Fq "def test_freecad_container_transfers_checkout_and_returns_evidence()" ||
    ! git show "origin/main:${test_path}" | grep -Fq '"--shm-size=1g" in action' ||
    ! git show "${rebase_commit}:${test_path}" | grep -Fq "def test_guarded_rebase_uses_the_verified_conflict_resolver"; then
    echo "::error::Refusing duplicated contract-test cleanup outside the exact deletion-only 97b837b9 commit and verified current-main contract."
    exit 1
  fi
  echo "::notice::Skipping exact 97b837b9 duplicate test-tail cleanup; retaining current main's canonical single-copy contract tests."
  git checkout origin/main -- "${test_path}"
  git add "${test_path}"
  if ! git rebase --skip; then
    rebase_merge="$(git rev-parse --git-path rebase-merge)"
    rebase_apply="$(git rev-parse --git-path rebase-apply)"
    if [[ -d "${rebase_merge}" || -d "${rebase_apply}" ]]; then
      bash tools/ci/guarded_rebase_conflict_entrypoint.sh
    else
      exit 1
    fi
  fi
elif [[ "${rebase_commit}" == "a9ecc40952cad7377c0ca148d6a3e9a30c25bdd3" ]] &&
  [[ "${conflicted_files}" == "tools/ci/resolve_guarded_rebase_conflicts.sh" ]]; then
  resolver_path="tools/ci/resolve_guarded_rebase_conflicts.sh"
  changed_paths="$(git diff-tree --no-commit-id --name-only -r "${rebase_commit}")"
  if [[ "${changed_paths}" != "${resolver_path}" ]] ||
    git diff --unified=0 "${rebase_commit}^" "${rebase_commit}" -- "${resolver_path}" | grep -Eq '^\+[^+]' ||
    ! git show "origin/main:${resolver_path}" | bash -n ||
    ! git show "origin/main:${resolver_path}" | grep -Fq "9a43f60fabacfcd894a560d58b10ed6bdd2533e6" ||
    ! git show "origin/main:${resolver_path}" | grep -Fq "a59f58d25537de846677f89a7858562cfcfc9672" ||
    ! git show "origin/main:${resolver_path}" | grep -Fq "f7cc118eb4aafafbaf1e5bcc7526140ad2e6f28e" ||
    ! git show "origin/main:${resolver_path}" | grep -Fq "bbd581e2df7ed83509755ef7a32850edd3441f49" ||
    ! git show "origin/main:${resolver_path}" | grep -Fq "99b9aa0e93e1a5e071a989c9b0a751dc2d8d6bbd" ||
    ! git show "origin/main:${resolver_path}" | grep -Fq "69999107b2e8888a5d179835b8297b21fef19d74"; then
    echo "::error::Refusing resolver-tail cleanup outside exact deletion-only a9ecc409 and verified current-main resolver."
    exit 1
  fi
  echo "::notice::Skipping exact a9ecc409 duplicate resolver-tail cleanup; retaining the complete syntactically valid current-main resolver."
  git checkout origin/main -- "${resolver_path}"
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
elif [[ "${rebase_commit}" == "fb42ac86ef9685bdfd90aa369fbb70f9da630d75" ]] &&
  [[ "${conflicted_files}" == "tests/test_runner_routing_contract.py" ]]; then
  test_path="tests/test_runner_routing_contract.py"
  changed_paths="$(git diff-tree --no-commit-id --name-only -r "${rebase_commit}")"
  if [[ "${changed_paths}" != "${test_path}" ]] ||
    ! git show "${rebase_commit}:${test_path}" | grep -Fq "9a43f60fabacfcd894a560d58b10ed6bdd2533e6" ||
    ! git show "origin/main:${test_path}" | grep -Fq "9a43f60fabacfcd894a560d58b10ed6bdd2533e6" ||
    ! git show "origin/main:${test_path}" | grep -Fq "tests/test_build_visual_gifs.py"; then
    echo "::error::Refusing resolver-source assertion restoration outside the exact fb42ac86 test-only commit and verified current-main assertion."
    exit 1
  fi
  echo "::notice::Skipping exact fb42ac86 resolver-source assertion restoration; current main already has the corrected source assertion."
  git checkout origin/main -- "${test_path}"
  git add "${test_path}"
  if ! git rebase --skip; then
    rebase_merge="$(git rev-parse --git-path rebase-merge)"
    rebase_apply="$(git rev-parse --git-path rebase-apply)"
    if [[ -d "${rebase_merge}" || -d "${rebase_apply}" ]]; then
      bash tools/ci/guarded_rebase_conflict_entrypoint.sh
    else
      exit 1
    fi
  fi
elif [[ "${rebase_commit}" == "5a4f3ff1bc99a09b064e0b9bfebbf611628b633f" ]] &&
  [[ "${conflicted_files}" == "tests/test_runner_routing_contract.py" ]]; then
  test_path="tests/test_runner_routing_contract.py"
  changed_paths="$(git diff-tree --no-commit-id --name-only -r "${rebase_commit}")"
  if [[ "${changed_paths}" != "${test_path}" ]] ||
    git diff --unified=0 "${rebase_commit}^" "${rebase_commit}" -- "${test_path}" | grep -Eq '^\+[^+]' ||
    ! git show "origin/main:${test_path}" | grep -Fq "def test_guarded_rebase_uses_the_verified_conflict_resolver" ||
    ! git show "origin/main:${test_path}" | grep -Fq "def test_freecad_container_transfers_checkout_and_returns_evidence()" ||
    ! git show "origin/main:${test_path}" | grep -Fq '"--shm-size=1g" in action' ||
    git show "${rebase_commit}:${test_path}" | grep -Fq "def test_freecad_container_transfers_checkout_and_returns_evidence()"; then
    echo "::error::Refusing duplicate test-tail removal outside the exact deletion-only 5a4f3ff1 commit and verified current-main contract."
    exit 1
  fi
  echo "::notice::Skipping exact 5a4f3ff1 duplicate test-tail removal; retaining current main's complete repository-container contract."
  git checkout origin/main -- "${test_path}"
  git add "${test_path}"
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
