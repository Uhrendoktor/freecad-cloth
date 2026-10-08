# Keep the Pivy extension on the same SWIG-era runtime as the FreeCAD 1.1.0
# conda build. The unpinned r3 image can resolve a newer Pivy build that is
# incompatible with FreeCAD's embedded SWIG runtime and breaks Coin scene-graph
# conversion with "No SWIG wrapped library loaded".
FROM ghcr.io/uhrendoktor/freecad-cloth/freecad-ci:freecad-1.1.0-py312-r3

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN /opt/conda/bin/mamba install -y -n freecad -c conda-forge \
        "pivy=0.6.10" \
    && /opt/conda/envs/freecad/bin/python -c "import pivy; from pivy import coin; print('pivy-module=' + pivy.__file__); print('coin=' + coin.SoDB.getVersion()); print('coin-module=' + coin.__file__)" \
    && /opt/conda/envs/freecad/bin/python -m pip install --no-cache-dir \
        pypbd==2.2.2 \
        triangle==20250106 \
        pytest \
        hypothesis==6.168.3 \
    && /opt/conda/envs/freecad/bin/python -c "import importlib.metadata, pypbd; print('pypbd=' + importlib.metadata.version('pyPBD')); print('pypbd_module=' + pypbd.__file__)" \
    && cat > /opt/pypbd-provenance.txt <<'EOF'
Package: pyPBD
Version: 2.2.2
Import: pypbd
Wheel: pypbd-2.2.2-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl
SHA256: a5147c9c73e6f51e2963f664e90336a8813a4b37f19c2c20369e5b1ddad59834
EOF

ENV PYTHONPATH=/workspace
