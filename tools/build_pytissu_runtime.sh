#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${1:-$ROOT/artifacts/pytissu-runtime}"
if [[ "$OUT_DIR" != /* ]]; then
  OUT_DIR="$ROOT/$OUT_DIR"
fi
mkdir -p "$OUT_DIR"
OUT_DIR="$(cd "$OUT_DIR" && pwd)"
# Docker bind mounts require absolute host paths; keep this normalization fail-closed.
IMAGE="${FREECAD_IMAGE:-ghcr.io/uhrendoktor/freecad-cloth/freecad-ci:freecad-1.1.0-py312-r3}"
TISSU_COMMIT="c28a3c7504ddc782bef844ab5bd4cd0bde14b628"

mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.whl "$OUT_DIR"/pytissu-provenance.txt

docker pull "$IMAGE"

docker run --rm --security-opt seccomp=unconfined \
  -v "$ROOT:/workspace:ro" \
  -v "$OUT_DIR:/out" \
  -e TISSU_COMMIT="$TISSU_COMMIT" \
  "$IMAGE" bash -lc '
    set -euo pipefail

    apt-get update -qq
    apt-get install -y --no-install-recommends build-essential cmake git libomp-dev
    rm -rf /var/lib/apt/lists/*

    rm -rf /tmp/Tissu
    git clone --quiet https://github.com/evanrock520-ciencias/Tissu.git /tmp/Tissu
    cd /tmp/Tissu
    git checkout --quiet "$TISSU_COMMIT"
    test "$(git rev-parse HEAD)" = "$TISSU_COMMIT"

    git apply --check /workspace/tools/tissu-mesh-collider-inside.patch
    git apply /workspace/tools/tissu-mesh-collider-inside.patch

    sed -i "s/^version = \"1.1.0\"$/version = \"1.1.0+freecad_cloth.1\"/" pyproject.toml

    python3 -m pip install --no-cache-dir setuptools wheel
    python3 scripts/build.py --no-viewer --no-tracy --jobs 2

    ctest --test-dir build --output-on-failure -R "MeshCollider\\."

    rm -f /out/*.whl
    python3 -m pip wheel . --no-deps --no-build-isolation -w /out
    WHEEL="$(find /out -maxdepth 1 -name "*.whl" -print -quit)"
    test -n "$WHEEL"

    python3 -m pip install --no-cache-dir --force-reinstall --no-deps "$WHEEL"
    python3 -c "import tissu; print(tissu.__file__)"

    {
      echo "source_repo=https://github.com/evanrock520-ciencias/Tissu"
      echo "source_commit=$TISSU_COMMIT"
      echo "patch_sha256=$(sha256sum /workspace/tools/tissu-mesh-collider-inside.patch | awk "{print \$1}")"
      echo "wheel=$(basename "$WHEEL")"
      echo "python=$(python3 --version)"
      echo "cmake=$(cmake --version | head -n 1)"
      echo "compiler=$(c++ --version | head -n 1)"
    } > /out/pytissu-provenance.txt
  '
