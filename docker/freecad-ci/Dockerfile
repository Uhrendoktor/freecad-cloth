FROM ghcr.io/uhrendoktor/freecad-cloth/freecad-ci:freecad-1.1.0-py312-r3

ARG TISSU_COMMIT=c28a3c7504ddc782bef844ab5bd4cd0bde14b628

LABEL org.opencontainers.image.source="https://github.com/Uhrendoktor/freecad-cloth"
LABEL org.opencontainers.image.description="Published FreeCAD 1.1.0 CI image with reproducibly patched Tissu"
LABEL org.opencontainers.image.tissu.source-commit="$TISSU_COMMIT"

COPY tissu-mesh-collider.patch /tmp/tissu-mesh-collider.patch

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN set -euxo pipefail \
    && apt-get update -qq \
    && apt-get install -y --no-install-recommends build-essential git libomp-dev \
    && rm -rf /var/lib/apt/lists/* \
    && mamba create -y -p /opt/tissu-build -c conda-forge cmake=3.29.6 \
    && export PATH=/opt/tissu-build/bin:$PATH \
    && TISSU_SRC=/tmp/tissu-src \
    && git clone --quiet https://github.com/evanrock520-ciencias/Tissu.git "$TISSU_SRC" \
    && git -C "$TISSU_SRC" checkout --detach "$TISSU_COMMIT" \
    && test "$(git -C "$TISSU_SRC" rev-parse HEAD)" = "$TISSU_COMMIT" \
    && /opt/conda/envs/freecad/bin/python - "$TISSU_SRC/core/CMakeLists.txt" <<'PY' \
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")

source_block = """    src/io/SceneExporter.cpp
    src/io/AlembicExporter.cpp
    src/io/StateSerializer.cpp"""
source_replacement = """    src/io/SceneExporter.cpp
    src/io/StateSerializer.cpp"""
dependency_block = """if(NOT TARGET Alembic::Alembic)
    find_package(Alembic REQUIRED)
endif()
if(NOT TARGET Imath::Imath)
    find_package(Imath REQUIRED)
endif()

"""
link_block = """target_link_libraries(TissuCore PUBLIC 
    Alembic::Alembic 
    Imath::Imath
)
"""

for label, old, new in (
    ("Alembic source entry", source_block, source_replacement),
    ("Alembic dependency discovery", dependency_block, ""),
    ("Alembic link block", link_block, ""),
):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"headless Tissu patch expected exactly one {label}, found {count}")
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
PY
    && git -C "$TISSU_SRC" apply --check /tmp/tissu-mesh-collider.patch \
    && git -C "$TISSU_SRC" apply /tmp/tissu-mesh-collider.patch \
    && git -C "$TISSU_SRC" diff --check \
    && EXPECTED_PATCH_FILES="$(printf '%s\n' \
         core/CMakeLists.txt \
         core/include/physics/MeshCollider.hpp \
         core/src/physics/MeshCollider.cpp \
         tests/physics/test_mesh_collider.cpp | LC_ALL=C sort)" \
    && test "$(LC_ALL=C git -C "$TISSU_SRC" diff --name-only | LC_ALL=C sort)" = "$EXPECTED_PATCH_FILES" \
    && test -n "$(git -C "$TISSU_SRC" status --porcelain)" \
    && cmake -S "$TISSU_SRC" -B "$TISSU_SRC/build" \
      -DCMAKE_BUILD_TYPE=Release \
      -DTISSU_BUILD_VIEWER=OFF \
      -DTISSU_ENABLE_TRACY=OFF \
      -DPython_EXECUTABLE=/opt/conda/envs/freecad/bin/python \
      -DPython3_EXECUTABLE=/opt/conda/envs/freecad/bin/python \
    && cmake --build "$TISSU_SRC/build" --target unit_tests _cloth_sdk_core --parallel "$(nproc)" \
    && "$TISSU_SRC/build/bin/unit_tests" --gtest_filter="MeshCollider.*" \
    && /opt/conda/envs/freecad/bin/python -m pip install --no-cache-dir --force-reinstall --no-deps "$TISSU_SRC" \
    && /opt/conda/envs/freecad/bin/python -m pip install --no-cache-dir triangle==20250106 \
    && /opt/conda/envs/freecad/bin/python -c "import importlib.metadata, tissu, triangle, pytest; assert importlib.metadata.version('pytissu') == '1.1.0'; assert importlib.metadata.version('triangle') == '20250106'; print('Tissu', tissu.__file__); print('pytissu', importlib.metadata.version('pytissu')); print('Triangle', triangle.__file__); print('triangle', importlib.metadata.version('triangle')); print('pytest', pytest.__version__)" \
    && TISSU_PATCH_SHA256="$(sha256sum /tmp/tissu-mesh-collider.patch | awk '{print $1}')" \
    && { \
         echo "tissu-source-repository=https://github.com/evanrock520-ciencias/Tissu.git"; \
         echo "tissu-source-commit=$TISSU_COMMIT"; \
         echo "tissu-patch-sha256=$TISSU_PATCH_SHA256"; \
         echo "tissu-build=cmake-headless-source"; \
         echo "tissu-headless-build-optimization=exclude-AlembicExporter"; \
         echo "tissu-base-image=ghcr.io/uhrendoktor/freecad-cloth/freecad-ci:freecad-1.1.0-py312-r3"; \
         echo "tissu-cpp-regression=MeshCollider.*"; \
         echo "tissu-cpp-regression-result=passed"; \
         echo "tissu-patched-source-files=$EXPECTED_PATCH_FILES"; \
         echo "tissu-python-package-version=$( /opt/conda/envs/freecad/bin/python -c "import importlib.metadata; print(importlib.metadata.version('pytissu'))" )"; \
         echo "tissu-python-module=$( /opt/conda/envs/freecad/bin/python -c "import tissu; print(tissu.__file__)" )"; \
         echo "tissu-triangle-version=$( /opt/conda/envs/freecad/bin/python -c "import importlib.metadata; print(importlib.metadata.version('triangle'))" )"; \
         echo "tissu-cmake-version=$( cmake --version | head -n1 )"; \
       } | tee /opt/tissu-provenance.txt \
    && rm -rf "$TISSU_SRC" /tmp/tissu-mesh-collider.patch /opt/tissu-build \
    && mamba clean --all --yes

ENV PATH=/opt/conda/envs/freecad/bin:/opt/conda/bin:$PATH
WORKDIR /workspace
