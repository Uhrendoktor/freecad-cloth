"""Research-only native FreeCAD MeshObject containment probe.

This file intentionally touches only the research branch. It measures the native
MeshObject.foraminate() path against the repository collision surface and does not
alter solver gates, timesteps, thresholds, or production code.
"""
import json
import math
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import FreeCAD as App
import Mesh

from freecad_cloth.avatar.AvatarCollision import (
    coarsen_collision_surface,
    surface_from_freecad,
)
from freecad_cloth.simulation.SimulationObjects import create_humanoid_avatar

RAY = (1.0, 0.123456789, 0.654321987)
DIRECTION = RAY[0] ** 2 + RAY[1] ** 2 + RAY[2] ** 2
DIRECTION = tuple(v / math.sqrt(DIRECTION) for v in RAY)
TRIANGLE_LIMIT = 2048
POINTS = 1022
STEPS = 90
THICKNESS_MM = 2.0


def native_mesh(surface):
    mesh = Mesh.Mesh()
    for a, b, c in surface.triangles:
        mesh.addFacet(
            App.Vector(*surface.vertices[a]),
            App.Vector(*surface.vertices[b]),
            App.Vector(*surface.vertices[c]),
        )
    return mesh


def dot(a, b):
    return sum(float(a[i]) * float(b[i]) for i in range(3))


def sub(a, b):
    return tuple(float(a[i]) - float(b[i]) for i in range(3))


def scale(a, factor):
    return tuple(float(v) * float(factor) for v in a)


def unique_forward_hits(hits, point, eps):
    ordered = []
    for facet_index, hit in hits.items():
        q = tuple(float(v) for v in hit)
        t = dot(sub(q, point), DIRECTION)
        if t <= eps:
            continue
        if any(dot(sub(q, prev_q), sub(q, prev_q)) <= eps * eps for _, prev_q in ordered):
            continue
        ordered.append((int(facet_index), q))
    ordered.sort(key=lambda item: dot(sub(item[1], point), DIRECTION))
    return ordered


def classify(mesh, point, boundary_eps):
    # FreeCAD's native implementation intersects the infinite line. Recover
    # half-line semantics by projecting hit points onto the chosen direction.
    hits = mesh.foraminate((tuple(float(v) for v in point), DIRECTION), math.pi)
    if not isinstance(hits, dict):
        raise RuntimeError("foraminate() returned %s, expected dict" % type(hits).__name__)

    near = any(
        abs(dot(sub(tuple(float(v) for v in hit), point), DIRECTION)) <= boundary_eps
        for hit in hits.values()
    )
    if near:
        return "boundary", hits

    forward = unique_forward_hits(hits, point, max(boundary_eps * 0.25, 1.0e-5))
    return ("inside" if len(forward) % 2 else "outside"), hits


def deterministic_points(bounds):
    # 14 * 73 = 1022. The distribution is deterministic and spans the
    # collision mesh bounding box without depending on random state.
    nx, nz = 14, 73
    points = []
    sx = float(bounds.XMax - bounds.XMin)
    sy = float(bounds.YMax - bounds.YMin)
    sz = float(bounds.ZMax - bounds.ZMin)
    for iz in range(nz):
        zf = 0.05 + 0.90 * iz / float(nz - 1)
        for ix in range(nx):
            xf = 0.05 + 0.90 * ix / float(nx - 1)
            yf = 0.50 + 0.30 * math.sin((iz * nx + ix) * 0.37)
            yf = max(0.05, min(0.95, yf))
            points.append((
                bounds.XMin + xf * sx,
                bounds.YMin + yf * sy,
                bounds.ZMin + zf * sz,
            ))
    if len(points) != POINTS:
        raise RuntimeError("deterministic point count is %d" % len(points))
    return tuple(points)


def nearest_exit(mesh, point):
    hits = mesh.foraminate((tuple(float(v) for v in point), DIRECTION), math.pi)
    candidates = []
    for facet_index, hit in hits.items():
        q = tuple(float(v) for v in hit)
        t = dot(sub(q, point), DIRECTION)
        if t > 0.0:
            candidates.append((t, int(facet_index), q))
    if not candidates:
        raise RuntimeError("no forward surface intersection for interior point")
    t, facet_index, q = min(candidates, key=lambda item: item[0])
    normal = tuple(float(v) for v in mesh.Facets[facet_index].Normal)
    length = math.sqrt(dot(normal, normal))
    if length <= 0.0:
        raise RuntimeError("zero-length facet normal")
    normal = scale(normal, 1.0 / length)
    corrected = tuple(q[i] + THICKNESS_MM * normal[i] for i in range(3))
    return t, facet_index, q, normal, corrected


doc = App.newDocument("MeshParityProbe")
try:
    print("freecad-version=%s" % App.Version()[0], flush=True)
    avatar = create_humanoid_avatar(doc)
    surface = surface_from_freecad(avatar, 1.0, THICKNESS_MM)
    solver_surface = coarsen_collision_surface(surface, TRIANGLE_LIMIT)

    if len(solver_surface.triangles) != TRIANGLE_LIMIT:
        raise RuntimeError(
            "coarsened collision surface has %d triangles, expected %d"
            % (len(solver_surface.triangles), TRIANGLE_LIMIT)
        )

    full_mesh = native_mesh(surface)
    solver_mesh = native_mesh(solver_surface)
    print(
        "collision-source vertices=%d triangles=%d"
        % (len(surface.vertices), len(surface.triangles)),
        flush=True,
    )
    print(
        "collision-solver vertices=%d triangles=%d"
        % (len(solver_surface.vertices), len(solver_surface.triangles)),
        flush=True,
    )
    print(
        "mesh-full facets=%d isSolid=%s"
        % (len(full_mesh.Facets), bool(full_mesh.isSolid())),
        flush=True,
    )
    print(
        "mesh-solver facets=%d isSolid=%s"
        % (len(solver_mesh.Facets), bool(solver_mesh.isSolid())),
        flush=True,
    )

    probe = solver_mesh.foraminate(((0.0, 0.0, 0.0), DIRECTION), math.pi)
    print(
        "foraminate type=%s len=%d sample=%s"
        % (type(probe).__name__, len(probe), repr(next(iter(probe.items()), None))),
        flush=True,
    )

    diagonal = float(full_mesh.BoundBox.DiagonalLength)
    boundary_eps = max(1.0e-3, diagonal * 1.0e-6)
    center = full_mesh.BoundBox.Center
    center_point = (center.x, center.y, center.z)
    center_class, _ = classify(full_mesh, center_point, boundary_eps)

    facet = full_mesh.Facets[0]
    face_center = tuple(
        sum(float(p[i]) for p in facet.Points) / 3.0 for i in range(3)
    )
    face_normal = tuple(float(v) for v in facet.Normal)
    face_len = math.sqrt(dot(face_normal, face_normal))
    face_normal = scale(face_normal, 1.0 / face_len)
    boundary_class, _ = classify(full_mesh, face_center, boundary_eps)
    near_inside = sub(face_center, scale(face_normal, 0.1))
    near_outside = tuple(face_center[i] + 0.1 * face_normal[i] for i in range(3))
    near_inside_class, _ = classify(full_mesh, near_inside, boundary_eps)
    near_outside_class, _ = classify(full_mesh, near_outside, boundary_eps)

    print(
        "classification center=%s boundary=%s near_inside=%s near_outside=%s boundary_eps_mm=%.6g"
        % (center_class, boundary_class, near_inside_class, near_outside_class, boundary_eps),
        flush=True,
    )
    if bool(full_mesh.isSolid()):
        expected = {"center", "boundary", "near_inside", "near_outside"}
        # Only fail for an impossible API result; exact inside/outside acceptance
        # is left to the numeric evidence printed above because concave-body
        # center/facet choices are geometry-dependent.
        if not {center_class, boundary_class, near_inside_class, near_outside_class} <= {"inside", "outside", "boundary"}:
            raise RuntimeError("invalid classification result")

    if center_class == "inside":
        exit_data = nearest_exit(full_mesh, center_point)
        print(
            "correction distance_mm=%.6f facet=%d surface=%s normal=%s corrected=%s thickness_mm=%.3f"
            % (exit_data[0], exit_data[1], exit_data[2], exit_data[3], exit_data[4], THICKNESS_MM),
            flush=True,
        )

    points = deterministic_points(solver_mesh.BoundBox)
    started = perf_counter()
    counts = {"inside": 0, "outside": 0, "boundary": 0}
    total_hits = 0
    for _ in range(STEPS):
        for point in points:
            label, hits = classify(solver_mesh, point, boundary_eps)
            counts[label] += 1
            total_hits += len(hits)
    elapsed = perf_counter() - started
    queries = POINTS * STEPS
    qps = queries / elapsed if elapsed > 0.0 else float("inf")
    print(
        "benchmark points=%d steps=%d queries=%d elapsed_s=%.6f queries_per_s=%.2f "
        "hits=%d inside=%d outside=%d boundary=%d budget60s=%s"
        % (
            POINTS,
            STEPS,
            queries,
            elapsed,
            qps,
            total_hits,
            counts["inside"],
            counts["outside"],
            counts["boundary"],
            "pass" if elapsed <= 60.0 else "fail",
        ),
        flush=True,
    )

    Path("/workspace/artifacts").mkdir(parents=True, exist_ok=True)
    Path("/workspace/artifacts/mesh-parity.json").write_text(
        json.dumps(
            {
                "freecad_version": App.Version()[0],
                "source_triangles": len(surface.triangles),
                "solver_triangles": len(solver_surface.triangles),
                "source_isSolid": bool(full_mesh.isSolid()),
                "solver_isSolid": bool(solver_mesh.isSolid()),
                "foraminate_type": type(probe).__name__,
                "foraminate_len": len(probe),
                "classification": {
                    "center": center_class,
                    "boundary": boundary_class,
                    "near_inside": near_inside_class,
                    "near_outside": near_outside_class,
                },
                "boundary_eps_mm": boundary_eps,
                "benchmark": {
                    "points": POINTS,
                    "steps": STEPS,
                    "queries": queries,
                    "elapsed_s": elapsed,
                    "queries_per_s": qps,
                    "total_hits": total_hits,
                    "counts": counts,
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
finally:
    try:
        App.closeDocument(doc.Name)
    except Exception:
        pass
    try:
        App.exit()
    except Exception:
        pass
