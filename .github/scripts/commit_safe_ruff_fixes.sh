#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${PR_BRANCH:-}" || -z "${PR_HEAD_SHA:-}" ]]; then
  echo "::error::PR branch and expected head are required."
  exit 2
fi

remote_sha="$(git ls-remote origin "refs/heads/${PR_BRANCH}" | cut -f1)"
if [[ "$remote_sha" != "$PR_HEAD_SHA" ]]; then
  echo "::error::PR branch moved during validation; refusing to push safe fixes."
  exit 1
fi

mapfile -d '' changed_files < <(git diff --name-only -z -- '*.py' '*.pyi')
if (("${#changed_files[@]}" == 0)); then
  echo "No Ruff source changes to commit."
  exit 0
fi

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add -- "${changed_files[@]}"
git diff --cached --check
git commit -m "style: apply safe Ruff fixes across Python sources"
git push --force-with-lease="refs/heads/${PR_BRANCH}:${PR_HEAD_SHA}" origin "HEAD:refs/heads/${PR_BRANCH}"
