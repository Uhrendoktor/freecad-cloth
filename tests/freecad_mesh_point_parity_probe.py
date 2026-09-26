import math
import sys
import time
from pathlib import Path

import FreeCAD as App
import MeshPart
import Part

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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
        ab = (bx - ax, by - ay, bz - ay)
        ac = (cx0 - ax, cy0 - ay, cz0 - az)
        normal = (
            ab[1] * ac[2] - ab[2] * ac[1],
            ab[2] * ac[0] - ab[0] * ac[2],
            ab[0] * ac[1] - ab[1] * ac[0],
        )
        rel = (ax - cx, ay - cy, az - cz)
        volume6 += normal[0] * rel[0] + normal[1] * rel[1] + normal[2] * rel[2]
    return volume6 / 6.0


def _mesh_parity(surface):
    signed_volume = _signed_surface_volume(surface.vertices, surface.triangles)
    transformed_vertices, transformed_triangles = _to_tissu_mesh(surface)
    transformed_volume = _signed_surface_volume(transformed_vertices, transformed_triangles)
    return signed_volume, transformed_volume


def main():
    doc = App.newDocument("MeshParityProbe")
    try:
        cube = doc.addObject("Mesh::Feature", "Probe")
        cube.Mesh = MeshPart.meshFromShape(
            Shape=Part.makeBox(10.0, 12.0, 14.0),
            LinearDeflection=0.5,
            AngularDeflection=0.5,
        )
        doc.recompute()

        for name, p in (
            ("inside", App.Vector(5, 6, 7)),
            ("outside", App.Vector(15, 6, 7)),
            ("boundary", App.Vector(0, 6, 7)),
        ):
            hits = cube.Mesh.foraminate(
                ((p.x, p.y, p.z), (1.0, 0.0, 0.0)),
                math.pi,
            )
            print(name, type(hits).__name__, len(hits), hits[:3])

        print("cube_solid", bool(cube.Mesh.isSolid()))
        start = time.perf_counter()
        count = 0
        for _ in range(1000):
            hits = cube.Mesh.foraminate(
                ((5.0, 6.0, 7.0), (1.0, 0.0, 0.0)),
                math.pi,
            )
            count += len(hits)
        elapsed = time.perf_counter() - start
        print("benchmark_calls=1000 hits=%d elapsed_ms=%.3f" % (count, elapsed * 1000.0))

        avatar = create_humanoid_avatar(doc)
        surface = surface_from_freecad(avatar, 1.0, 2.0)
        source_volume, tissu_volume = _mesh_parity(surface)
        print(
            "avatar_mesh_parity vertices=%d triangles=%d source_signed_volume=%.6f tissu_signed_volume=%.6f"
            % (len(surface.vertices), len(surface.triangles), source_volume, tissu_volume)
        )
        if not (math.isfinite(source_volume) and math.isfinite(tissu_volume)):
            raise RuntimeError("avatar signed-volume parity is non-finite")
        if source_volume == 0.0 or tissu_volume == 0.0:
            raise RuntimeError("avatar signed-volume parity is degenerate")
        if (source_volume > 0.0) != (tissu_volume > 0.0):
            raise RuntimeError("FreeCAD->Tissu transform flips closed-mesh signed orientation")
    finally:
        try:
            App.closeDocument(doc.Name)
        finally:
            App.exit()


if __name__ == "__main__":
    main()
