FROM condaforge/miniforge3:25.3.1-0

LABEL org.opencontainers.image.source="https://github.com/Uhrendoktor/freecad-cloth"
LABEL org.opencontainers.image.description="FreeCAD 1.1.0 conda-forge CI image using Python 3.12 for freecad-cloth with Tissu cloth backend"

RUN apt-get update -qq \
    && apt-get install -y --no-install-recommends xvfb openbox x11-utils build-essential cmake git libomp-dev \
    && rm -rf /var/lib/apt/lists/* \
    && mamba create -y -n freecad -c conda-forge python=3.12 pip freecad=1.1.0 \
    && /opt/conda/envs/freecad/bin/python -m pip install --no-cache-dir pytissu==1.1.0 triangle==20250106 pytest \
    && /opt/conda/envs/freecad/bin/python -c "import tissu, triangle, pytest; print('Tissu', tissu.__file__); print('Triangle', triangle.__file__); print('pytest', pytest.__version__)" \
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
