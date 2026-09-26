FROM condaforge/miniforge3:25.3.1-0

ARG TISSU_SOURCE_COMMIT=c28a3c7504ddc782bef844ab5bd4cd0bde14b628

COPY docker/freecad-ci/apply-tissu-contact-fix.py /tmp/apply-tissu-contact-fix.py

LABEL org.opencontainers.image.source="https://github.com/Uhrendoktor/freecad-cloth"
LABEL org.opencontainers.image.description="FreeCAD 1.1.0 conda-forge CI image using Python 3.12 for freecad-cloth with Tissu cloth backend"

RUN apt-get update -qq \
    && apt-get install -y --no-install-recommends xvfb openbox x11-utils build-essential cmake git libomp-dev \
    && rm -rf /var/lib/apt/lists/* \
    && mamba create -y -n freecad -c conda-forge python=3.12 pip freecad=1.1.0 \
    && /opt/conda/envs/freecad/bin/python -m pip install --no-cache-dir pytissu==1.1.0 triangle==20250106 pytest \
    && rm -rf /tmp/Tissu \
    && git clone --no-checkout --filter=blob:none https://github.com/evanrock520-ciencias/Tissu.git /tmp/Tissu \
    && cd /tmp/Tissu \
    && git fetch --depth 1 origin "$TISSU_SOURCE_COMMIT" \
    && git checkout --detach "$TISSU_SOURCE_COMMIT" \
    && test "$(git rev-parse HEAD)" = "$TISSU_SOURCE_COMMIT" \
    && /opt/conda/envs/freecad/bin/python /tmp/apply-tissu-contact-fix.py \

    && /opt/conda/envs/freecad/bin/cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_POLICY_VERSION_MINIMUM=3.5 -DBENCHMARK_ENABLE_WERROR=OFF -DTISSU_BUILD_VIEWER=OFF -DTISSU_ENABLE_TRACY=OFF -DCMAKE_C_FLAGS=-Wno-c2y-extensions \
    && /opt/conda/envs/freecad/bin/cmake --build build --config Release --target _cloth_sdk_core unit_tests --parallel 2 \
    && /opt/conda/envs/freecad/bin/python -m pip install --no-cache-dir --no-deps --no-build-isolation --force-reinstall . \
    && /opt/conda/envs/freecad/bin/python -m pip check \
    && /tmp/Tissu/build/bin/unit_tests --gtest_filter='MeshCollider.*' \
    && /opt/conda/envs/freecad/bin/python -c "import tissu, triangle, pytest; print('Tissu', tissu.__file__); print('Tissu source', '$TISSU_SOURCE_COMMIT'); print('Triangle', triangle.__file__); print('pytest', pytest.__version__)" \
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
