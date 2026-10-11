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


# Bake the pinned HM08 source mesh into each CI image. The checksum protects
# skeleton/weight vertex indexing, and the inherited environment prevents every
# fresh validation container from fetching the same mesh again.
RUN /opt/conda/envs/freecad/bin/python - <<'PY'
from hashlib import sha256
from pathlib import Path
from urllib.request import Request, urlopen

url = (
    "https://raw.githubusercontent.com/makehumancommunity/makehuman/"
    "1f508f6083b2f823dab15de924b3bde72e08d77c9/makehuman/data/3dobjs/base.obj"
)
expected_sha256 = "8e761e6624b8f54536409135d1636da63b32486a90d4897f84e121d144f6fb4c"
destination = Path("/opt/freecad-cloth/assets/makehuman-hm08-base.obj")
destination.parent.mkdir(parents=True, exist_ok=True)
request = Request(url, headers={"User-Agent": "freecad-cloth-ci/1"})
with urlopen(request, timeout=60) as response:
    payload = response.read()
actual_sha256 = sha256(payload).hexdigest()
if actual_sha256 != expected_sha256:
    raise SystemExit(
        f"pinned MakeHuman base mesh checksum mismatch: {actual_sha256}"
    )
destination.write_bytes(payload)
print(
    f"bundled-makehuman-base={destination} sha256={actual_sha256} "
    f"bytes={len(payload)}",
    flush=True,
)
PY

ENV FREECAD_CLOTH_AVATAR_MESH=/opt/freecad-cloth/assets/makehuman-hm08-base.obj

# Keep the Pivy build shipped with the FreeCAD image. Rebuilding it inside
# this image is not reliable because the image does not expose a standalone
# SWIG build toolchain even though FreeCAD embeds the SWIG runtime.
RUN /opt/conda/envs/freecad/bin/python -c "import pivy; from pivy import coin; print('bundled-pivy-module=' + pivy.__file__); print('bundled-coin=' + coin.SoDB.getVersion()); print('bundled-coin-module=' + coin.__file__)" \
    && /opt/conda/envs/freecad/bin/python -m pip install --no-cache-dir \
        --extra-index-url https://download.pytorch.org/whl/cpu \
        "torch==2.8.0+cpu" \
    && /opt/conda/envs/freecad/bin/python -m pip install --no-cache-dir \
        pypbd==2.2.2 \
        triangle==20250106 \
        "pydantic>=2.11,<3" \
        "pillow>=11,<13" \
        "networkx>=3,<4" \
        "rtree>=1,<2" \
        "trimesh>=4,<6" \
        "scipy>=1.14,<2" \
        "shapely>=2,<3" \
        "anny[warp]>=0.5,<0.6" \
        "clad-body[anny]>=0.6.1,<0.7" \
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

# Prebuild Anny's MakeHuman-compatible rig and the same local-change basis used
# by the Cloth adapter. Each GUI acceptance container then reuses the cache
# instead of rebuilding the parametric body model on every fresh container.
ENV ANNY_CACHE_DIR=/opt/freecad-cloth/cache/anny
RUN mkdir -p "$ANNY_CACHE_DIR" && chmod 777 "$ANNY_CACHE_DIR" && \
    /opt/conda/envs/freecad/bin/python - <<'PY'
import json
from dataclasses import replace
from pathlib import Path

import torch
from anny import Anny
from anny.models.model_data import RigConfig, TopologyConfig
from anny.paths import get_anny_root_dir
from clad_body.load.anny import build_anny_apose

root = Path(get_anny_root_dir())
metadata = json.loads((root / "data/mpfb2/targets/target.json").read_text(encoding="utf-8"))
terms = (
    "measure-bust-circ", "measure-underbust-circ", "measure-waist-circ",
    "measure-hips-circ", "measure-upperarm-circ", "measure-thigh-circ",
    "measure-knee-circ", "measure-calf-circ", "measure-neck-circ",
    "measure-shoulder-dist", "torso-scale-horiz", "breast-volume-vert-up",
)
labels = set()
for group, group_data in metadata.items():
    if group == "genitals" or not isinstance(group_data, dict):
        continue
    for category in group_data.get("categories", []):
        opposites = category.get("opposites", {})
        for side in ("left", "right", "unsided"):
            positive = opposites.get(f"positive-{side}", "")
            negative = opposites.get(f"negative-{side}", "")
            if positive and negative and any(term in positive for term in terms):
                labels.add(positive)
if "breast-volume-vert-up" not in labels:
    raise SystemExit("Anny breast morph target is missing from the installed assets")
rig = replace(
    RigConfig.from_string("makehuman"),
    bone_orientation="blender",
    root_identity_orientation=True,
)
topology = replace(
    TopologyConfig.from_string("makehuman"),
    nudity_edits=False,
    remove_unattached_vertices=False,
    triangulate_faces=True,
    eyes=False,
    tongue=False,
    submodel="body",
)
model = Anny(
    rig=rig,
    topology=topology,
    local_changes=sorted(labels),
    phenotypes="all",
    pose_parameterization="local-bone",
).to(dtype=torch.float32, device="cpu")
base_ids = model.base_mesh_vertex_indices.detach().cpu().tolist()
if base_ids[:13380] != list(range(13380)):
    raise SystemExit("Anny topology does not preserve the legacy HM08 body vertex index order")
phenotypes = {name: 0.5 for name in model.phenotype_labels}
phenotypes.update({"gender": 0.5, "age": 0.667, "african": 1 / 3, "asian": 1 / 3, "caucasian": 1 / 3})
local_changes = {name: 0.0 for name in model.local_change_labels}
pose = build_anny_apose(model, torch.device("cpu"))
with torch.no_grad():
    output = model(
        pose_parameters=pose,
        phenotype_kwargs={name: torch.tensor([value], dtype=torch.float32) for name, value in phenotypes.items()},
        local_changes_kwargs={name: torch.tensor([value], dtype=torch.float32) for name, value in local_changes.items()},
        pose_parameterization="local-bone",
        return_bone_ends=True,
    )
print(
    f"anny-prewarm=passed vertices={output['vertices'].shape[1]} faces={model.faces.shape[0]} "
    f"local-change-targets={len(labels)} cache={__import__('os').environ['ANNY_CACHE_DIR']}",
    flush=True,
)
PY

ENV PYTHONPATH=/workspace
