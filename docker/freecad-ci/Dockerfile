FROM condaforge/miniforge3:25.3.1-0

ARG TISSU_COMMIT=c28a3c7504ddc782bef844ab5bd4cd0bde14b628

LABEL org.opencontainers.image.source="https://github.com/Uhrendoktor/freecad-cloth"
LABEL org.opencontainers.image.description="FreeCAD 1.1.0 conda-forge CI image using Python 3.12 for freecad-cloth with Tissu cloth backend"
LABEL org.opencontainers.image.tissu.source-commit="$TISSU_COMMIT"

COPY tissu-mesh-collider.patch /tmp/tissu-mesh-collider.patch

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN set -euxo pipefail \
    && apt-get update -qq \
    && apt-get install -y --no-install-recommends xvfb openbox x11-utils build-essential git libomp-dev \
    && rm -rf /var/lib/apt/lists/* \
    && mamba create -y -n freecad -c conda-forge python=3.12 pip freecad=1.1.0 cmake=3.29.6 \
    && export PATH=/opt/conda/envs/freecad/bin:$PATH \
    && TISSU_SRC=/tmp/tissu-src \
    && git clone --quiet https://github.com/evanrock520-ciencias/Tissu.git "$TISSU_SRC" \
    && git -C "$TISSU_SRC" checkout --detach "$TISSU_COMMIT" \
    && test "$(git -C "$TISSU_SRC" rev-parse HEAD)" = "$TISSU_COMMIT" \
    && git -C "$TISSU_SRC" apply --check /tmp/tissu-mesh-collider.patch \
    && git -C "$TISSU_SRC" apply /tmp/tissu-mesh-collider.patch \
    && git -C "$TISSU_SRC" diff --check \
    && test -n "$(git -C "$TISSU_SRC" status --porcelain)" \
    && cmake -S "$TISSU_SRC" -B "$TISSU_SRC/build" \
      -DCMAKE_BUILD_TYPE=Release \
      -DTISSU_BUILD_VIEWER=OFF \
      -DTISSU_ENABLE_TRACY=OFF \
      -DPython_EXECUTABLE=/opt/conda/envs/freecad/bin/python \
      -DPython3_EXECUTABLE=/opt/conda/envs/freecad/bin/python \
    && cmake --build "$TISSU_SRC/build" --target unit_tests _cloth_sdk_core --parallel "$(nproc)" \
    && "$TISSU_SRC/build/bin/unit_tests" --gtest_filter="MeshCollider.*" \
    && /opt/conda/envs/freecad/bin/python -m pip install --no-cache-dir --no-deps "$TISSU_SRC" \
    && /opt/conda/envs/freecad/bin/python -m pip install --no-cache-dir \
      triangle==20250106 pytest numpy tqdm matplotlib imageio \
    && /opt/conda/envs/freecad/bin/python -c "import importlib.metadata, tissu, triangle, pytest; assert importlib.metadata.version('pytissu') == '1.1.0'; print('Tissu', tissu.__file__); print('pytissu', importlib.metadata.version('pytissu')); print('Triangle', triangle.__file__); print('pytest', pytest.__version__)" \
    && TISSU_PATCH_SHA256="$(sha256sum /tmp/tissu-mesh-collider.patch | awk '{print $1}')" \
    && { \
         echo "tissu-source-repository=https://github.com/evanrock520-ciencias/Tissu.git"; \
         echo "tissu-source-commit=$TISSU_COMMIT"; \
         echo "tissu-patch-sha256=$TISSU_PATCH_SHA256"; \
         echo "tissu-build=cmake-headless-source"; \
         echo "tissu-cpp-regression=MeshCollider.*"; \
         echo "tissu-cpp-regression-result=passed"; \
         echo "tissu-python-package-version=$( /opt/conda/envs/freecad/bin/python -c "import importlib.metadata; print(importlib.metadata.version('pytissu'))" )"; \
         echo "tissu-python-module=$( /opt/conda/envs/freecad/bin/python -c "import tissu; print(tissu.__file__)" )"; \
       } | tee /opt/tissu-provenance.txt \
    && mamba clean --all --yes \
    && rm -rf "$TISSU_SRC" /tmp/tissu-mesh-collider.patch \
    && mkdir -p /opt/freecad \
    && printf '%s\n' '#!/bin/sh' 'exec /opt/conda/envs/freecad/bin/freecad "$@"' > /opt/freecad/AppRun \
    && chmod +x /opt/freecad/AppRun

ENV DISPLAY=:99 \
    QT_X11_NO_MITSHM=1 \
    QT_QPA_PLATFORM=xcb \
    LIBGL_ALWAYS_SOFTWARE=1 \
    PATH=/opt/conda/envs/freecad/bin:/opt/conda/bin:$PATH

WORKDIR /workspace
