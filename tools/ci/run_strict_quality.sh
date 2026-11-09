#!/usr/bin/env bash
# Copyright (C) 2026 FreeCAD Cloth contributors
set -euo pipefail

if [[ $# -ne 1 || -z "$1" ]]; then
  echo "Usage: run_strict_quality.sh <immutable-pbd-image-tag>" >&2
  exit 2
fi

image="$1"
workspace="${GITHUB_WORKSPACE:-$(git rev-parse --show-toplevel)}"
workspace="$(cd "$workspace" && pwd -P)"
tool_cache="${RUNNER_TOOL_CACHE:-$HOME/.cache}"
cache_root="${tool_cache}/freecad-cloth"
mkdir -p "$cache_root/home" "$cache_root/pip-cache" "$cache_root/pre-commit" "$cache_root/xdg"

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

exec docker run --rm --init --security-opt seccomp=unconfined --shm-size=1g \
  --user "$(id -u):$(id -g)" \
  --volume "$workspace:/workspace:rw" \
  --volume "$cache_root:/runner-cache:rw" \
  --workdir /workspace \
  --env RUNNER_TOOL_CACHE=/runner-cache \
  --env PIP_CACHE_DIR=/runner-cache/pip-cache \
  --env PRE_COMMIT_HOME=/runner-cache/pre-commit \
  --env HOME=/runner-cache/home \
  --env XDG_CACHE_HOME=/runner-cache/xdg \
  --env QUALITY_IMAGE_ID="$image_id" \
  --env WORKSPACE_CACHE_KEY="$workspace_key" \
  --env GITHUB_ACTIONS=true \
  "$image" /opt/conda/envs/freecad/bin/python tools/ci/strict_quality.py
