import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import json
import math
from pathlib import Path

import FreeCAD as App

from freecad_cloth.avatar.AvatarCollision import surface_from_freecad
from freecad_cloth.simulation.SimulationObjects import create_humanoid_avatar
from freecad_cloth.simulation.TissuBackend import _to_tissu_mesh


def _signed_surface_volume(vertices, triangles):
    if not vertices or not triangles:
        raise RuntimeError("surface has no geometry")
    cx = sum(float(v[0]) for v in vertices) / len(vertices)
    cy = sum(float(v[1]) for v in vertices) / len(vertices)
    cz = sum(float(v[2]) for v in vertices) / len(vertices)
    volume6 = 0.0
    for a, b, c in triangles:
        ax, ay, az = (float(v) for v in vertices[a])
        bx, by, bz = (float(v) for v in vertices[b])
        cx0, cy0, cz0 = (float(v) for v in vertices[c])
        ab = (bx - ax, by - ay, bz - az)
        ac = (cx0 - ax, cy0 - ay, cz0 - az)
        normal = (
            ab[1] * ac[2] - ab[2] * ac[1],
            ab[2] * ac[0] - ab[0] * ac[2],
            ab[0] * ac[1] - ab[1] * ac[0],
        )
        rel = (ax - cx, ay - cy, az - cz)
        volume6 += normal[0] * rel[0] + normal[1] * rel[1] + normal[2] * rel[2]
    return volume6 / 6.0


result_path = Path("/workspace/artifacts/mesh-parity.json")
result_path.parent.mkdir(parents=True, exist_ok=True)
doc = App.newDocument("MeshParityProbe")
try:
    print("avatar-parity=build-start", flush=True)
    avatar = create_humanoid_avatar(doc)
    print("avatar-parity=build-pass", flush=True)
    surface = surface_from_freecad(avatar, 1.0, 2.0)
    print(
        "avatar-parity=surface-pass vertices=%d triangles=%d"
        % (len(surface.vertices), len(surface.triangles)),
        flush=True,
    )
    source_volume = _signed_surface_volume(surface.vertices, surface.triangles)
    transformed_vertices, transformed_triangles = _to_tissu_mesh(surface)
    tissu_volume = _signed_surface_volume(transformed_vertices, transformed_triangles)
    print(
        "avatar-parity source_signed_volume=%.6f tissu_signed_volume=%.6f"
        % (source_volume, tissu_volume),
        flush=True,
    )
    if not (math.isfinite(source_volume) and math.isfinite(tissu_volume)):
        raise RuntimeError("avatar signed-volume parity is non-finite")
    if source_volume == 0.0 or tissu_volume == 0.0:
        raise RuntimeError("avatar signed-volume parity is degenerate")
    if (source_volume > 0.0) != (tissu_volume > 0.0):
        raise RuntimeError("FreeCAD->Tissu transform flips closed-mesh signed orientation")
    result = {
        "freecad_version": App.Version()[0],
        "vertices": len(surface.vertices),
        "triangles": len(surface.triangles),
        "source_signed_volume": source_volume,
        "tissu_signed_volume": tissu_volume,
        "same_signed_orientation": (source_volume > 0.0) == (tissu_volume > 0.0),
    }
    result_path.write_text(json.dumps(result, sort_keys=True) + "\n", encoding="utf-8")
    print("avatar-parity=passed same-signed-orientation", flush=True)
finally:
    try:
        App.closeDocument(doc.Name)
    except Exception:
        pass
    try:
        App.exit()
    except Exception:
        pass
