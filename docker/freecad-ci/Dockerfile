# Keep the Pivy extension on the same SWIG-era runtime as the FreeCAD 1.1.0
# conda build. The unpinned r3 image can resolve a newer Pivy build that is
# incompatible with FreeCAD's embedded SWIG runtime and breaks Coin scene-graph
# conversion with "No SWIG wrapped library loaded".
FROM ghcr.io/uhrendoktor/freecad-cloth/freecad-ci:freecad-1.1.0-py312-r3

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN /opt/conda/envs/freecad/bin/python - <<'PY'
from pathlib import Path
import re
import sys

root = Path(sys.prefix)
print("=== base-runtime-before-pivy probe-20261008b ===", flush=True)
try:
    import pivy
    from pivy import coin
    print("pivy-module=" + str(getattr(pivy, "__file__", "unknown")), flush=True)
    print("coin-version=" + str(coin.SoDB.getVersion()), flush=True)
    for candidate in sorted(Path(pivy.__file__).parent.glob("_coin*.so")):
        data = candidate.read_bytes()
        matches = sorted(set(x.decode("ascii") for x in re.findall(rb"swig_runtime_data([0-9]+)", data)))
        print("pivy-binary=" + str(candidate) + " swig=" + (",".join(matches) or "none"), flush=True)
except Exception as exc:
    print("pivy-error=" + repr(exc), flush=True)

for scan_root in (root / "lib", root / "lib" / "python3.12" / "site-packages"):
    for pattern in ("FreeCAD*.so*", "libFreeCAD*.so*", "_FreeCAD*.so*"):
        for candidate in sorted(scan_root.rglob(pattern)):
            try:
                data = candidate.read_bytes()
            except OSError:
                continue
            matches = sorted(set(x.decode("ascii") for x in re.findall(rb"swig_runtime_data([0-9]+)", data)))
            if matches:
                print("freecad-binary=" + str(candidate) + " swig=" + ",".join(matches), flush=True)
PY

# Keep the Pivy build shipped with the FreeCAD image. Rebuilding it inside
# this image is not reliable because the image does not expose a standalone
# SWIG build toolchain even though FreeCAD embeds the SWIG runtime.
RUN /opt/conda/envs/freecad/bin/python -c "import pivy; from pivy import coin; print('bundled-pivy-module=' + pivy.__file__); print('bundled-coin=' + coin.SoDB.getVersion()); print('bundled-coin-module=' + coin.__file__)" \
    && /opt/conda/envs/freecad/bin/python -m pip install --no-cache-dir \
        pypbd==2.2.2 \
        triangle==20250106 \
        "pydantic>=2.11,<3" \
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
