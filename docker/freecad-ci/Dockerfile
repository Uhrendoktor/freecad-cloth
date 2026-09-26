FROM condaforge/miniforge3:25.3.1-0

LABEL org.opencontainers.image.source="https://github.com/Uhrendoktor/freecad-cloth"
LABEL org.opencontainers.image.description="FreeCAD 1.1.0 CI image with pinned fail-closed Tissu runtime"

ARG TISSU_SOURCE_COMMIT=c28a3c7504ddc782bef844ab5bd4cd0bde14b628

COPY tissu-mesh-collider-inside.patch /tmp/tissu-mesh-collider-inside.patch

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN set -euxo pipefail \
    && apt-get update -qq \
    && apt-get install -y --no-install-recommends xvfb openbox x11-utils build-essential git libomp-dev \
    && rm -rf /var/lib/apt/lists/* \
    && mamba create -y -n freecad -c conda-forge python=3.12 pip freecad=1.1.0 cmake=3.29.6 \
    && /opt/conda/envs/freecad/bin/python -m pip install --no-cache-dir triangle==20250106 pytest numpy tqdm matplotlib imageio \
    && git clone --depth 1 https://github.com/evanrock520-ciencias/Tissu.git /tmp/Tissu \
    && cd /tmp/Tissu \
    && git fetch --depth 1 origin "$TISSU_SOURCE_COMMIT" \
    && git checkout --detach "$TISSU_SOURCE_COMMIT" \
    && git apply --check /tmp/tissu-mesh-collider-inside.patch \
    && git apply /tmp/tissu-mesh-collider-inside.patch \
    && git diff --check \
    && /opt/conda/envs/freecad/bin/cmake -S /tmp/Tissu -B /tmp/Tissu/build -DCMAKE_BUILD_TYPE=Release -DTISSU_BUILD_VIEWER=OFF -DTISSU_ENABLE_TRACY=OFF \
    && /opt/conda/envs/freecad/bin/cmake --build /tmp/Tissu/build --target _cloth_sdk_core unit_tests --parallel "$(nproc)" \
    && /tmp/Tissu/build/bin/unit_tests --gtest_filter='MeshCollider.*' \
    && /opt/conda/envs/freecad/bin/python -m pip install --no-cache-dir --no-deps /tmp/Tissu \
    && /opt/conda/envs/freecad/bin/python -c "import tissu, triangle, pytest; print('Tissu', tissu.__file__); print('Triangle', triangle.__file__); print('pytest', pytest.__version__)" \
    && patch_hash="$(sha256sum /tmp/tissu-mesh-collider-inside.patch | cut -d' ' -f1)" \
    && printf '%s\n' "source_commit=$TISSU_SOURCE_COMMIT" "patch_sha256=$patch_hash" "build_mode=headless-source" "mesh_collider_tests=passed" "installed_module=$(/opt/conda/envs/freecad/bin/python -c 'import tissu; print(tissu.__file__)')" > /opt/tissu-provenance.txt \
    && rm -rf /tmp/Tissu /tmp/tissu-mesh-collider-inside.patch \
    && mamba clean --all --yes \
    && mkdir -p /opt/freecad \
    && printf '%s\n' '#!/bin/sh' 'exec /opt/conda/envs/freecad/bin/freecad "$@"' > /opt/freecad/AppRun \
    && chmod +x /opt/freecad/AppRun

ENV DISPLAY=:99 \
    QT_X11_NO_MITSHM=1 \
    QT_QPA_PLATFORM=xcb \
    LIBGL_ALWAYS_SOFTWARE=1 \
    PATH=/opt/conda/envs/freecad/bin:/opt/conda/bin:$PATH

WORKDIR /workspace
