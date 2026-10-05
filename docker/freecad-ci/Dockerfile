FROM ghcr.io/uhrendoktor/freecad-cloth/freecad-ci:freecad-1.1.0-py312-r3

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN /opt/conda/envs/freecad/bin/python -m pip install --no-cache-dir \
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
