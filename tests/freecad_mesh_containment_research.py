"""Research-only validation of native FreeCAD MeshObject.foraminate()."""

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

from freecad_cloth.avatar.AvatarCollision import coarsen_collision_surface, surface_from_freecad
from freecad_cloth.simulation.SimulationObjects import create_humanoid_avatar

POINTS = 1022
STEPS = 90
TRIANGLES = 2048
THICKNESS_MM = 2.0
RAY = (1.0, 0.123456789, 0.654321987)
RAY_LEN = math.sqrt(sum(v * v for v in RAY))
DIRECTION = tuple(v / RAY_LEN for v in RAY)


def dot(a, b):
    return sum(float(a[i]) * float(b[i]) for i in range(3))


def sub(a, b):
    return tuple(float(a[i]) - float(b[i]) for i in range(3))


def add(a, b):
    return tuple(float(a[i]) + float(b[i]) for i in range(3))


def scale(a, s):
    return tuple(float(v) * float(s) for v in a)


def norm(v):
    length = math.sqrt(dot(v, v))
    if length <= 0.0:
        raise RuntimeError("zero-length vector")
    return scale(v, 1.0 / length)


def to_native_mesh(surface):
    mesh = Mesh.Mesh()
    for a, b, c in surface.triangles:
        mesh.addFacet(
            App.Vector(*surface.vertices[a]),
            App.Vector(*surface.vertices[b]),
            App.Vector(*surface.vertices[c]),
        )
    return mesh


def foraminate(mesh, point):
    result = mesh.foraminate(tuple(float(v) for v in point), DIRECTION, math.pi)
    if not isinstance(result, dict):
        raise RuntimeError("foraminate() returned %s, expected dict" % type(result).__name__)
    for facet_index, hit in result.items():
        if not isinstance(facet_index, int):
            raise RuntimeError("foraminate() key is %r, expected int" % type(facet_index).__name__)
        if not isinstance(hit, tuple) or len(hit) != 3:
            raise RuntimeError("foraminate() value is %r, expected 3-tuple" % (type(hit).__name__,))
    return result


def unique_forward_hits(hits, point, eps):
    unique = []
    eps2 = eps * eps
    for facet_index, raw_hit in hits.items():
        hit = tuple(float(v) for v in raw_hit)
        t = dot(sub(hit, point), DIRECTION)
        if t <= eps:
            continue
        duplicate = any(
            dot(sub(hit, existing_hit), sub(hit, existing_hit)) <= eps2
            for _, existing_hit in unique
        )
        if not duplicate:
            unique.append((int(facet_index), hit))
    unique.sort(key=lambda item: dot(sub(item[1], point), DIRECTION))
    return unique


def classify(mesh, point, boundary_eps):
    """Infinite-line native intersection + deterministic forward-ray parity."""
    hits = foraminate(mesh, point)
    near_boundary = any(
        abs(dot(sub(tuple(float(v) for v in hit), point), DIRECTION)) <= boundary_eps
        for hit in hits.values()
    )
    if near_boundary:
        return "boundary", hits

    forward = unique_forward_hits(
        hits,
        point,
        max(1.0e-5, boundary_eps * 0.25),
    )
    return ("inside" if len(forward) & 1 else "outside"), hits


def deterministic_points(bounds):
    nx, nz = 14, 73  # 1022 exactly
    sx = float(bounds.XMax - bounds.XMin)
    sy = float(bounds.YMax - bounds.YMin)
    sz = float(bounds.ZMax - bounds.ZMin)
    result = []
    for iz in range(nz):
        zf = 0.05 + 0.90 * iz / float(nz - 1)
        for ix in range(nx):
            xf = 0.05 + 0.90 * ix / float(nx - 1)
            yf = max(0.05, min(0.95, 0.50 + 0.30 * math.sin((iz * nx + ix) * 0.37)))
            result.append((
                bounds.XMin + xf * sx,
                bounds.YMin + yf * sy,
                bounds.ZMin + zf * sz,
            ))
    if len(result) != POINTS:
        raise RuntimeError("deterministic point count is %d" % len(result))
    return tuple(result)


def correction_primitive(mesh, interior_point, thickness, boundary_eps):
    """Small host-side primitive assuming an interior point and one hit.

    The facet normal is oriented locally by two epsilon offset classifications;
    then the corrected particle is exactly surface_point + outward_normal*thickness.
    """
    hits = foraminate(mesh, interior_point)
    candidates = []
    for facet_index, raw_hit in hits.items():
        hit = tuple(float(v) for v in raw_hit)
        t = dot(sub(hit, interior_point), DIRECTION)
        if t > boundary_eps:
            candidates.append((t, int(facet_index), hit))
    if not candidates:
        raise RuntimeError("interior point has no forward surface intersection")

    t, facet_index, surface_point = min(candidates, key=lambda item: item[0])
    normal = norm(tuple(float(v) for v in mesh.Facets[facet_index].Normal))
    probe_delta = max(10.0 * boundary_eps, 1.0e-3)
    plus = classify(mesh, add(surface_point, scale(normal, probe_delta)), boundary_eps)[0]
    minus = classify(mesh, sub(surface_point, scale(normal, probe_delta)), boundary_eps)[0]

    if plus == "outside" and minus != "outside":
        outward = normal
    elif minus == "outside" and plus != "outside":
        outward = scale(normal, -1.0)
    else:
        raise RuntimeError(
            "facet normal is not locally orientable: plus=%s minus=%s facet=%d"
            % (plus, minus, facet_index)
        )

    corrected = add(surface_point, scale(outward, thickness))
    return {
        "distance_mm": t,
        "facet_index": facet_index,
        "surface_point": surface_point,
        "outward_normal": outward,
        "corrected_point": corrected,
        "plus_side": plus,
        "minus_side": minus,
        "thickness_mm": thickness,
    }


doc = App.newDocument("MeshContainmentResearch")
try:
    print("freecad-version=%s" % App.Version()[0], flush=True)

    avatar = create_humanoid_avatar(doc)
    authored = surface_from_freecad(avatar, 1.0, THICKNESS_MM)
    solver_surface = coarsen_collision_surface(authored, TRIANGLES)

    if len(solver_surface.triangles) != TRIANGLES:
        raise RuntimeError(
            "coarsened collision surface has %d triangles, expected %d"
            % (len(solver_surface.triangles), TRIANGLES)
        )

    full_mesh = to_native_mesh(authored)
    solver_mesh = to_native_mesh(solver_surface)

    full_solid = bool(full_mesh.isSolid())
    solver_solid = bool(solver_mesh.isSolid())
    print("authored triangles=%d isSolid=%s" % (len(authored.triangles), full_solid), flush=True)
    print("solver triangles=%d isSolid=%s" % (len(solver_surface.triangles), solver_solid), flush=True)

    probe_result = foraminate(solver_mesh, (0.0, 0.0, 0.0))
    sample = next(iter(probe_result.items()), None)
    print(
        "foraminate return_type=%s len=%d sample=%s"
        % (type(probe_result).__name__, len(probe_result), repr(sample)),
        flush=True,
    )

    diagonal = float(full_mesh.BoundBox.DiagonalLength)
    boundary_eps = max(1.0e-3, diagonal * 1.0e-6)

    center = full_mesh.BoundBox.Center
    interior_point = (center.x, center.y, center.z)
    interior_class, _ = classify(full_mesh, interior_point, boundary_eps)

    facet = full_mesh.Facets[0]
    facet_points = facet.Points
    boundary_point = tuple(
        sum(float(p[i]) for p in facet_points) / 3.0
        for i in range(3)
    )
    raw_normal = norm(tuple(float(v) for v in facet.Normal))
    near_inside_point = sub(boundary_point, scale(raw_normal, 0.1))
    near_outside_point = add(boundary_point, scale(raw_normal, 0.1))
    boundary_class, _ = classify(full_mesh, boundary_point, boundary_eps)
    near_inside_class, _ = classify(full_mesh, near_inside_point, boundary_eps)
    near_outside_class, _ = classify(full_mesh, near_outside_point, boundary_eps)

    print(
        "classification center=%s boundary=%s near_inside=%s near_outside=%s boundary_eps_mm=%.6g"
        % (
            interior_class,
            boundary_class,
            near_inside_class,
            near_outside_class,
            boundary_eps,
        ),
        flush=True,
    )

    correction = None
    if interior_class == "inside":
        correction = correction_primitive(
            full_mesh,
            interior_point,
            THICKNESS_MM,
            boundary_eps,
        )
        print("correction=%s" % json.dumps(correction, sort_keys=True), flush=True)

    points = deterministic_points(solver_mesh.BoundBox)
    counts = {"inside": 0, "outside": 0, "boundary": 0}
    total_hits = 0

    started = perf_counter()
    for _step in range(STEPS):
        for point in points:
            label, hits = classify(solver_mesh, point, boundary_eps)
            counts[label] += 1
            total_hits += len(hits)
    elapsed = perf_counter() - started
    queries = POINTS * STEPS
    qps = queries / elapsed if elapsed > 0.0 else float("inf")

    print(
        "benchmark points=%d steps=%d queries=%d elapsed_s=%.6f queries_per_s=%.2f "
        "inside=%d outside=%d boundary=%d total_hits=%d budget_60s=%s"
        % (
            POINTS,
            STEPS,
            queries,
            elapsed,
            qps,
            counts["inside"],
            counts["outside"],
            counts["boundary"],
            total_hits,
            "pass" if elapsed <= 60.0 else "fail",
        ),
        flush=True,
    )

    result = {
        "freecad_version": App.Version()[0],
        "foraminate": {
            "return_type": type(probe_result).__name__,
            "sample": sample,
        },
        "authored": {
            "triangles": len(authored.triangles),
            "isSolid": full_solid,
        },
        "solver": {
            "triangles": len(solver_surface.triangles),
            "isSolid": solver_solid,
        },
        "classification": {
            "center": interior_class,
            "boundary": boundary_class,
            "near_inside": near_inside_class,
            "near_outside": near_outside_class,
            "boundary_eps_mm": boundary_eps,
        },
        "correction": correction,
        "benchmark": {
            "points": POINTS,
            "steps": STEPS,
            "queries": queries,
            "elapsed_s": elapsed,
            "queries_per_s": qps,
            "counts": counts,
            "total_hits": total_hits,
            "budget_60s": elapsed <= 60.0,
        },
    }

    Path("/workspace/artifacts").mkdir(parents=True, exist_ok=True)
    Path("/workspace/artifacts/mesh-containment.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
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
