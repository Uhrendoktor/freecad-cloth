#!/usr/bin/env bash
# Copyright (C) 2026 FreeCAD Cloth contributors
set -euo pipefail

mode="${2:-}"
if [[ $# -lt 1 || $# -gt 2 || -z "$1" || ( $# -eq 2 && "$mode" != "--ruff-autofix" ) ]]; then
  echo "Usage: run_strict_quality.sh <immutable-pbd-image-tag> [--ruff-autofix]" >&2
  exit 2
fi

image="$1"
workspace="${GITHUB_WORKSPACE:-$(git rev-parse --show-toplevel)}"
if [[ ! -f "$workspace/tools/ci/strict_quality.py" ]]; then
  echo "::error::Strict-quality source is missing from the runner workspace: $workspace/tools/ci/strict_quality.py" >&2
  exit 1
fi
echo "strict-quality-workspace=$workspace"

# The runner checkout is a linked worktree, whose .git file points outside the
# Docker daemon's filesystem namespace. Transfer a self-contained Git bundle
# containing this exact HEAD and its base ref instead of copying that pointer.
bundle_branch="quality-${GITHUB_RUN_ID:-$$}-${GITHUB_RUN_ATTEMPT:-1}"
bundle_ref="refs/heads/$bundle_branch"
head_sha="$(git -C "$workspace" rev-parse HEAD)"
base_ref="${GITHUB_BASE_REF:-main}"
base_ref_name="refs/remotes/origin/$base_ref"
if ! base_sha="$(git -C "$workspace" rev-parse --verify "$base_ref_name")"; then
  echo "::error::The fetched pull-request base ref is missing: $base_ref_name" >&2
  exit 1
fi
temp_root="${RUNNER_TEMP:-${TMPDIR:-/tmp}}"
mkdir -p "$temp_root"
bundle_file="$temp_root/freecad-cloth-$bundle_branch.bundle"
cache_volume="freecad-cloth-quality-cache"
container_name="freecad-cloth-quality-${GITHUB_RUN_ID:-$$}-${GITHUB_RUN_ATTEMPT:-1}"
container_id=""

cleanup() {
  if [[ -n "$container_id" ]]; then
    docker rm -f "$container_id" >/dev/null 2>&1 || true
  fi
  git -C "$workspace" update-ref -d "$bundle_ref" >/dev/null 2>&1 || true
  rm -f "$bundle_file" "${temp_root:-/tmp}/freecad-cloth-ruff-autofix-${GITHUB_RUN_ID:-0}.patch"
}
trap cleanup EXIT

git -C "$workspace" update-ref "$bundle_ref" "$head_sha"
git -C "$workspace" bundle create "$bundle_file" "$bundle_ref" "$base_ref_name"
git -C "$workspace" bundle verify "$bundle_file" >/dev/null

docker volume create "$cache_volume" >/dev/null
if ! docker image inspect "$image" >/dev/null 2>&1; then
  if [[ -z "${GH_TOKEN:-}" ]]; then
    echo "::error::Pinned FreeCAD image is missing and GH_TOKEN is unavailable."
    exit 1
  fi
  printf '%s' "$GH_TOKEN" | docker login ghcr.io --username "${GITHUB_ACTOR:-github-actions}" --password-stdin >/dev/null
  docker pull "$image"
fi
image_id="$(docker image inspect --format '{{.Id}}' "$image")"
workspace_key="$(printf '%s' "$workspace" | sha256sum | cut -c1-12)"

container_id="$(docker create --name "$container_name" --init --security-opt seccomp=unconfined --shm-size=1g \
  --volume "$cache_volume:/runner-cache:rw" \
  --workdir /tmp \
  --env RUNNER_TOOL_CACHE=/runner-cache \
  --env PYTHONPATH="/opt/conda/envs/freecad/lib:/opt/conda/envs/freecad/Mod:/workspace" \
  --env LD_LIBRARY_PATH="/opt/conda/envs/freecad/lib" \
  --env TINI_SUBREAPER=1 \
  --env PIP_CACHE_DIR=/runner-cache/pip-cache \
  --env PRE_COMMIT_HOME=/runner-cache/pre-commit \
  --env HOME=/runner-cache/home \
  --env XDG_CACHE_HOME=/runner-cache/xdg \
  --env QUALITY_IMAGE_ID="$image_id" \
  --env WORKSPACE_CACHE_KEY="$workspace_key" \
  --env QUALITY_BUNDLE_BRANCH="$bundle_branch" \
  --env QUALITY_HEAD_SHA="$head_sha" \
  --env QUALITY_BASE_REF="$base_ref" \
  --env GITHUB_BASE_REF="$base_ref" \
  --env QUALITY_BASE_SHA="$base_sha" \
  --env QUALITY_MODE="${mode#--}" \
  --env GITHUB_ACTIONS=true \
  "$image" bash -lc '
    set -euo pipefail
    git clone --quiet --no-checkout --branch "$QUALITY_BUNDLE_BRANCH" \
      /tmp/freecad-cloth-quality.bundle /tmp/freecad-cloth-worktree
    git -C /tmp/freecad-cloth-worktree update-ref \
      "refs/remotes/origin/$QUALITY_BASE_REF" "$QUALITY_BASE_SHA"
    git -C /tmp/freecad-cloth-worktree checkout --quiet --detach "$QUALITY_HEAD_SHA"
    rm -rf /workspace
    mv /tmp/freecad-cloth-worktree /workspace
    cd /workspace
    test -f tools/ci/strict_quality.py
    test "$(git rev-parse HEAD)" = "$QUALITY_HEAD_SHA"
    git rev-parse --verify "origin/$QUALITY_BASE_REF"
    if [[ "$QUALITY_MODE" == "ruff-autofix" ]]; then
      exec /opt/conda/envs/freecad/bin/python -m tools.ci.strict_quality --ruff-autofix
    fi
    exec /opt/conda/envs/freecad/bin/python -m tools.ci.strict_quality
  ')"

docker cp "$bundle_file" "$container_id:/tmp/freecad-cloth-quality.bundle"
docker start --attach "$container_id"

if [[ "$mode" == "--ruff-autofix" ]]; then
  : "${GH_TOKEN:?GH_TOKEN is required for the explicit autofix push}"
  : "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}"
  : "${GITHUB_HEAD_REF:?GITHUB_HEAD_REF is required}"
  if [[ ! "$GITHUB_HEAD_REF" =~ ^[A-Za-z0-9._/-]+$ || "$GITHUB_HEAD_REF" == *".."* ]]; then
    echo "::error::Unsafe pull-request branch name; refusing to push autofixes."
    exit 2
  fi

  patch_file="$temp_root/freecad-cloth-ruff-autofix-${GITHUB_RUN_ID:-$$}.patch"
  docker cp "$container_id:/tmp/ruff-autofix.patch" "$patch_file"
  if [[ ! -s "$patch_file" ]]; then
    echo "ruff-autofix=no-changes"
    exit 0
  fi

  # The branch must still be the exact revision that was checked out for this run.
  remote_sha="$(git -C "$workspace" ls-remote origin "refs/heads/$GITHUB_HEAD_REF" | awk 'NR == 1 { print $1 }')"
  if [[ "$remote_sha" != "$head_sha" ]]; then
    echo "::error::PR branch advanced during Ruff autofix; refusing to apply stale changes."
    exit 1
  fi

  git -C "$workspace" apply --check "$patch_file"
  git -C "$workspace" apply "$patch_file"
  git -C "$workspace" add -u -- .
  if git -C "$workspace" diff --cached --quiet; then
    echo "ruff-autofix=no-staged-changes"
    exit 0
  fi

  changed_paths="$(git -C "$workspace" diff --cached --name-only)"
  while IFS= read -r path; do
    [[ "$path" == *.py || "$path" == *.pyi ]] || {
      echo "::error::Autofix patch changed a non-Python path: $path"
      exit 1
    }
  done <<< "$changed_paths"
  git -C "$workspace" diff --cached --check
  git -C "$workspace" config user.name "github-actions[bot]"
  git -C "$workspace" config user.email "41898282+github-actions[bot]@users.noreply.github.com"
  auth="$(printf 'x-access-token:%s' "$GH_TOKEN" | base64 | tr -d '\n')"
  git -C "$workspace" -c "http.extraheader=AUTHORIZATION: basic $auth" push \
    "https://github.com/$GITHUB_REPOSITORY.git" "HEAD:refs/heads/$GITHUB_HEAD_REF"
  echo "ruff-autofix=committed files=$(printf '%s\n' "$changed_paths" | wc -l | tr -d ' ')"
fi
