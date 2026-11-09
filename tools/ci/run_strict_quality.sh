#!/usr/bin/env bash
# Copyright (C) 2026 FreeCAD Cloth contributors
set -euo pipefail

if [[ $# -ne 1 || -z "$1" ]]; then
  echo "Usage: run_strict_quality.sh <immutable-pbd-image-tag>" >&2
  exit 2
fi

image="$1"
workspace="${GITHUB_WORKSPACE:-$(git rev-parse --show-toplevel)}"
if [[ ! -f "$workspace/tools/ci/strict_quality.py" ]]; then
  echo "::error::Strict-quality source is missing from the runner workspace: $workspace/tools/ci/strict_quality.py" >&2
  exit 1
fi
echo "strict-quality-workspace=$workspace"

# The runner checkout is not necessarily mounted into the Docker daemon's host
# namespace. Copy it through the Docker API instead of bind-mounting its path.
# Keep the dependency environment in a named volume so it survives job containers.
cache_volume="freecad-cloth-quality-cache"
docker volume create "$cache_volume" >/dev/null
# The quality container has no host filesystem mounts: both the checkout and
# its cache live in Docker-managed storage, so use the image's default user.

if ! docker image inspect "$image" >/dev/null 2>&1; then
  if [[ -z "${GH_TOKEN:-}" ]]; then
    echo "::error::Pinned FreeCAD image is missing and GH_TOKEN is unavailable."
    exit 1
  fi
  printf '%s' "$GH_TOKEN" | docker login ghcr.io --username "${GITHUB_ACTOR:-github-actions}" --password-stdin >/dev/null
  docker pull "$image"
fi
image_id="$(docker image inspect --format '{{.Id}}' "$image")"
# Inspect the native module locations and launcher environment before adapting
# the virtualenv preflight. AppRun itself may be a thin executable wrapper.
docker run --rm "$image" bash -lc '
  echo "=== freecad-runtime-probe ==="
  id
  echo "AppRun path: $(readlink -f /opt/freecad/AppRun)"
  sed -n "1,80p" /opt/freecad/AppRun
  echo "=== selected environment ==="
  env | grep -E "^(PATH|PYTHONPATH|LD_LIBRARY_PATH|QT_PLUGIN_PATH|QT_QPA_PLATFORM|CONDA_PREFIX)=" | sort || true
  echo "=== native module candidates ==="
  find /opt -type f -o -type l | grep -E "/(FreeCAD|FreeCADGui|Part|Mesh|MeshPart|Sketcher)([^/]*\\.so|\\.so[^/]*)$" | sort || true
  echo "=== FreeCAD module directories ==="
  find /opt/conda/envs/freecad -maxdepth 5 -type d | grep -E "/(Mod|lib|site-packages)(/|$)" | sort | head -120 || true
  echo "=== direct Python probe ==="
  /opt/conda/envs/freecad/bin/python -c "import sys; print(sys.executable); print(*sys.path, sep=chr(10))"
'
workspace_key="$(printf '%s' "$workspace" | sha256sum | cut -c1-12)"
container_name="freecad-cloth-quality-${GITHUB_RUN_ID:-$$}-${GITHUB_RUN_ATTEMPT:-1}"
container_id=""

cleanup() {
  if [[ -n "$container_id" ]]; then
    docker rm -f "$container_id" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

container_id="$(docker create --name "$container_name" --init --security-opt seccomp=unconfined --shm-size=1g \
  --volume "$cache_volume:/runner-cache:rw" \
  --workdir /workspace \
  --env RUNNER_TOOL_CACHE=/runner-cache \
  --env PIP_CACHE_DIR=/runner-cache/pip-cache \
  --env PRE_COMMIT_HOME=/runner-cache/pre-commit \
  --env HOME=/runner-cache/home \
  --env XDG_CACHE_HOME=/runner-cache/xdg \
  --env QUALITY_IMAGE_ID="$image_id" \
  --env WORKSPACE_CACHE_KEY="$workspace_key" \
  --env GITHUB_ACTIONS=true \
  "$image" /opt/conda/envs/freecad/bin/python tools/ci/strict_quality.py)"

docker cp -a "$workspace/." "$container_id:/workspace"
docker start --attach "$container_id"
