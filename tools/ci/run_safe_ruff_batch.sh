#!/usr/bin/env bash
# Copyright (C) 2026 FreeCAD Cloth contributors
set -euo pipefail

if [[ $# -ne 1 || -z "$1" ]]; then
  echo "Usage: run_safe_ruff_batch.sh <immutable-pbd-image-tag>" >&2
  exit 2
fi

quality_image="$1"
event_path="${GITHUB_EVENT_PATH:-}"
pr_title=""
pr_number=""
pr_head_repository=""
if [[ "$GITHUB_EVENT_NAME" == "pull_request" && -n "$event_path" && -f "$event_path" ]]; then
  pr_title="$(jq -r '.pull_request.title // ""' "$event_path")"
  pr_number="$(jq -r '.pull_request.number // ""' "$event_path")"
  pr_head_repository="$(jq -r '.pull_request.head.repo.full_name // ""' "$event_path")"
fi

if [[ "$GITHUB_EVENT_NAME" == "pull_request" \
  && "$pr_head_repository" == "$GITHUB_REPOSITORY" \
  && "$pr_title" == *"[apply-safe-ruff]"* ]]; then
  original_head="$(git rev-parse HEAD)"
  bash tools/ci/run_strict_quality.sh "$quality_image" --ruff-autofix
  git fetch --quiet origin "refs/heads/$GITHUB_HEAD_REF"
  updated_head="$(git rev-parse FETCH_HEAD)"
  if [[ "$updated_head" != "$original_head" ]]; then
    parent="$(git rev-list --parents -n 1 "$updated_head" | awk '{print $2}')"
    if [[ "$parent" != "$original_head" ]]; then
      echo "::error::Safe Ruff batch did not produce one direct child of the inspected PR head."
      exit 1
    fi
  fi
  if [[ -z "$pr_number" ]]; then
    echo "::error::PR number is missing; refusing to dispatch validation."
    exit 1
  fi
  gh workflow run commit-validation.yml --repo "$GITHUB_REPOSITORY" \
    --ref "$GITHUB_HEAD_REF" -f execution_mode=full -f pr_number="$pr_number"
  for _ in $(seq 1 30); do
    run_json="$(gh run list --repo "$GITHUB_REPOSITORY" --workflow "Commit validation" \
      --branch "$GITHUB_HEAD_REF" --event workflow_dispatch --limit 20 \
      --json databaseId,headSha,status,url \
      | jq -c --arg sha "$updated_head" '[.[] | select(.headSha == $sha)] | first // empty' || true)"
    if [[ -n "$run_json" ]]; then
      echo "exact-head-full-validation=$run_json"
      exit 0
    fi
    sleep 2
  done
  echo "::error::No full-validation run was observed for exact head $updated_head."
  exit 1
fi

bash tools/ci/run_strict_quality.sh "$quality_image"
