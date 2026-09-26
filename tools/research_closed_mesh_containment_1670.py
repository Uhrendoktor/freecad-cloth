"""Research probe for issue #1670: deterministic closed-mesh containment.

This file is intentionally diagnostic-only. It does not participate in production
simulation. It builds a BVH over the real HM08 authored surface, validates parity
classification/correction on convex and concave closed fixtures, then measures a
1022-particle x 90-step workload on the real 26k-face source.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import inf, sqrt
from pathlib import Path
from time import perf_counter


Vec = tuple[float, float, float]
Tri = tuple[int, int, int]
EPS = 1e-10


def sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def add(a: Vec, b: Vec) -> Vec:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def mul(a: Vec, s: float) -> Vec:
    return (a[0] * s, a[1] * s, a[2] * s)


def dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a: Vec, b: Vec) -> Vec:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def norm(a: Vec) -> float:
    return sqrt(dot(a, a))


def unit(a: Vec) -> Vec:
    n = norm(a)
    if n <= EPS:
        return (0.0, 0.0, 0.0)
    return mul(a, 1.0 / n)


def bbox(points: list[Vec], ids: list[int], triangles: tuple[Tri, ...]):
    lo = [inf, inf, inf]
    hi = [-inf, -inf, -inf]
    for tid in ids:
        for vi in triangles[tid]:
            p = points[vi]
            for axis in range(3):
                lo[axis] = min(lo[axis], p[axis])
                hi[axis] = max(hi[axis], p[axis])
    return (tuple(lo), tuple(hi))


def bbox_distance2(p: Vec, bmin: Vec, bmax: Vec) -> float:
    total = 0.0
    for axis in range(3):
        if p[axis] < bmin[axis]:
            d = bmin[axis] - p[axis]
        elif p[axis] > bmax[axis]:
            d = p[axis] - bmax[axis]
        else:
            d = 0.0
        total += d * d
    return total


def ray_box(origin: Vec, direction: Vec, bmin: Vec, bmax: Vec) -> bool:
    tmin = -inf
    tmax = inf
    for axis in range(3):
        d = direction[axis]
        if abs(d) <= EPS:
            if origin[axis] < bmin[axis] or origin[axis] > bmax[axis]:
                return False
            continue
        inv = 1.0 / d
        t0 = (bmin[axis] - origin[axis]) * inv
        t1 = (bmax[axis] - origin[axis]) * inv
        if t0 > t1:
            t0, t1 = t1, t0
        tmin = max(tmin, t0)
        tmax = min(tmax, t1)
        if tmax < max(tmin, 0.0):
            return False
    return tmax >= 0.0


def ray_triangle(origin: Vec, direction: Vec, a: Vec, b: Vec, c: Vec):
    edge1 = sub(b, a)
    edge2 = sub(c, a)
    pvec = cross(direction, edge2)
    det = dot(edge1, pvec)
    if abs(det) <= EPS:
        return None
    inv = 1.0 / det
    tvec = sub(origin, a)
    u = dot(tvec, pvec) * inv
    if u < -1e-11 or u > 1.0 + 1e-11:
        return None
    qvec = cross(tvec, edge1)
    v = dot(direction, qvec) * inv
    if v < -1e-11 or u + v > 1.0 + 1e-11:
        return None
    t = dot(edge2, qvec) * inv
    if t < -1e-9:
        return None
    w = 1.0 - u - v
    boundary = t <= 1e-9
    ambiguous = boundary or min(abs(u), abs(v), abs(w)) <= 1e-9
    return t, ambiguous


def closest_point_triangle(p: Vec, a: Vec, b: Vec, c: Vec):
    ab = sub(b, a)
    ac = sub(c, a)
    ap = sub(p, a)
    d1 = dot(ab, ap)
    d2 = dot(ac, ap)
    if d1 <= 0.0 and d2 <= 0.0:
        return a

    bp = sub(p, b)
    d3 = dot(ab, bp)
    d4 = dot(ac, bp)
    if d3 >= 0.0 and d4 <= d3:
        return b

    vc = d1 * d4 - d3 * d2
    if vc <= 0.0 and d1 >= 0.0 and d3 <= 0.0:
        t = d1 / max(EPS, d1 - d3)
        return add(a, mul(ab, t))

    cp = sub(p, c)
    d5 = dot(ab, cp)
    d6 = dot(ac, cp)
    if d6 >= 0.0 and d5 <= d6:
        return c

    vb = d5 * d2 - d1 * d6
    if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
        t = d2 / max(EPS, d2 - d6)
        return add(a, mul(ac, t))

    va = d3 * d6 - d5 * d4
    if va <= 0.0 and (d4 - d3) >= 0.0 and (d5 - d6) >= 0.0:
        bc = sub(c, b)
        t = (d4 - d3) / max(EPS, (d4 - d3) + (d5 - d6))
        return add(b, mul(bc, t))

    denom = 1.0 / max(EPS, va + vb + vc)
    v = vb * denom
    w = vc * denom
    return add(a, add(mul(ab, v), mul(ac, w)))


@dataclass(frozen=True)
class Node:
    bmin: Vec
    bmax: Vec
    left: int | None
    right: int | None
    ids: tuple[int, ...]


class TriangleBVH:
    def __init__(self, vertices: tuple[Vec, ...], triangles: tuple[Tri, ...], leaf_size: int = 8):
        self.vertices = vertices
        self.triangles = triangles
        self.leaf_size = max(2, int(leaf_size))
        self._centroids = tuple(
            tuple(sum(vertices[i][axis] for i in tri) / 3.0 for axis in range(3))
            for tri in triangles
        )
        ids = list(range(len(triangles)))
        self.nodes: list[Node] = []
        self._build(ids)

    def _build(self, ids: list[int]) -> int:
        bmin, bmax = bbox(self.vertices, ids, self.triangles)
        node_index = len(self.nodes)
        self.nodes.append(Node(bmin, bmax, None, None, ()))
        if len(ids) <= self.leaf_size:
            self.nodes[node_index] = Node(bmin, bmax, None, None, tuple(ids))
            return node_index
        spans = [bmax[i] - bmin[i] for i in range(3)]
        axis = max(range(3), key=spans.__getitem__)
        ids.sort(key=lambda tid: self._centroids[tid][axis])
        mid = len(ids) // 2
        left = self._build(ids[:mid])
        right = self._build(ids[mid:])
        self.nodes[node_index] = Node(bmin, bmax, left, right, ())
        return node_index

    def _ray_parity(self, p: Vec, direction: Vec):
        hits = 0
        ambiguous = False
        boundary = False
        stack = [0]
        while stack:
            ni = stack.pop()
            node = self.nodes[ni]
            if not ray_box(p, direction, node.bmin, node.bmax):
                continue
            if node.left is None:
                for tid in node.ids:
                    a, b, c = (self.vertices[i] for i in self.triangles[tid])
                    hit = ray_triangle(p, direction, a, b, c)
                    if hit is None:
                        continue
                    t, amb = hit
                    if t <= 1e-9:
                        boundary = True
                        continue
                    ambiguous = ambiguous or amb
                    hits += 1
                continue
            stack.append(node.left)
            stack.append(node.right)
        return hits & 1, ambiguous, boundary

    def classify(self, p: Vec, boundary_tol: float = 1e-6) -> str:
        # A direct zero-distance hit is boundary; ambiguous shared-edge/corner
        # ray hits trigger deterministic alternate directions.
        directions = (
            unit((1.0, 0.3713906763541037, 0.15915494309189535)),
            unit((-0.2113248654051871, 1.0, 0.5773502691896258)),
            unit((0.4472135954999579, -0.8017837257372732, 1.0)),
        )
        parities = []
        for direction in directions:
            parity, ambiguous, boundary = self._ray_parity(p, direction)
            if boundary:
                return "boundary"
            if ambiguous:
                continue
            parities.append(parity)
            if len(parities) == 2 and parities[0] == parities[1]:
                break
        if not parities:
            # Boundary is resolved by a nearest-surface query only in this rare
            # degenerate case, so normal queries remain a single-ray operation.
            q, _ = self.nearest(p)
            if norm(sub(q, p)) <= boundary_tol:
                return "boundary"
            raise RuntimeError("all deterministic containment rays were ambiguous")
        if all(v == 0 for v in parities):
            return "outside"
        if all(v == 1 for v in parities):
            return "inside"
        q, _ = self.nearest(p)
        if norm(sub(q, p)) <= boundary_tol:
            return "boundary"
        raise RuntimeError("containment rays disagreed away from boundary")

    def nearest(self, p: Vec):
        best2 = inf
        best_q = None
        best_tid = -1
        stack = [(0, 0.0)]
        while stack:
            ni, _ = stack.pop()
            node = self.nodes[ni]
            d2box = bbox_distance2(p, node.bmin, node.bmax)
            if d2box > best2:
                continue
            if node.left is None:
                for tid in node.ids:
                    tri = self.triangles[tid]
                    q = closest_point_triangle(p, *(self.vertices[i] for i in tri))
                    d2 = dot(sub(q, p), sub(q, p))
                    if d2 < best2 - 1e-15 or (abs(d2 - best2) <= 1e-15 and tid < best_tid):
                        best2 = d2
                        best_q = q
                        best_tid = tid
                continue
            left = self.nodes[node.left]
            right = self.nodes[node.right]
            dl = bbox_distance2(p, left.bmin, left.bmax)
            dr = bbox_distance2(p, right.bmin, right.bmax)
            if dl <= dr:
                stack.append((node.right, dr))
                stack.append((node.left, dl))
            else:
                stack.append((node.left, dl))
                stack.append((node.right, dr))
        if best_q is None:
            raise RuntimeError("BVH nearest query failed")
        return best_q, best_tid

    def correct_outward(self, p: Vec, clearance: float, boundary_tol: float = 1e-6):
        state = self.classify(p, boundary_tol)
        if state == "outside":
            return p, False
        q, tid = self.nearest(p)
        direction = unit(sub(q, p))
        if norm(direction) <= EPS:
            tri = self.triangles[tid]
            a, b, c = (self.vertices[i] for i in tri)
            direction = unit(cross(sub(b, a), sub(c, a)))
        target = add(q, mul(direction, max(float(clearance), boundary_tol)))
        state2 = self.classify(target, boundary_tol)
        if state2 != "outside":
            raise RuntimeError("nearest-outward correction did not cross the classified boundary")
        return target, True


def concave_l_prism() -> tuple[tuple[Vec, ...], tuple[Tri, ...]]:
    poly = ((0.0, 0.0), (3.0, 0.0), (3.0, 1.0), (1.0, 1.0), (1.0, 3.0), (0.0, 3.0))
    verts = tuple((x, y, z) for z in (0.0, 1.0) for x, y in poly)
    tris: list[Tri] = []
    top = tuple(range(6, 12))
    bottom = tuple(range(6))
    # Top CCW as viewed from +Z; bottom reversed.
    for i in range(1, 5):
        tris.append((top[0], top[i], top[i + 1]))
        tris.append((bottom[i + 1], bottom[i], bottom[0]))
    for i in range(6):
        j = (i + 1) % 6
        a, b = bottom[i], bottom[j]
        at, bt = top[i], top[j]
        tris.extend(((a, b, bt), (a, bt, at)))
    return verts, tuple(tris)


def cube() -> tuple[tuple[Vec, ...], tuple[Tri, ...]]:
    v = (
        (-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),
        (-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1),
    )
    return v, (
        (0,3,2),(0,2,1),       # -Z
        (4,5,6),(4,6,7),       # +Z
        (0,1,5),(0,5,4),       # -Y
        (1,2,6),(1,6,5),       # +X
        (2,3,7),(2,7,6),       # +Y
        (3,0,4),(3,4,7),       # -X
    )


def deterministic_points(surface: tuple[Vec, ...], count: int):
    xs = [p[0] for p in surface]
    ys = [p[1] for p in surface]
    zs = [p[2] for p in surface]
    lo = (min(xs), min(ys), min(zs))
    hi = (max(xs), max(ys), max(zs))
    span = tuple(hi[i] - lo[i] for i in range(3))
    state = 0x1670C0DE
    out = []
    for _ in range(count):
        values = []
        for axis in range(3):
            state = (1664525 * state + 1013904223) & 0xFFFFFFFF
            u = (state + 0.5) / 4294967296.0
            values.append(lo[axis] - 0.15 * span[axis] + u * 1.30 * span[axis])
        out.append((values[0], values[1], values[2]))
    return tuple(out)


def validate_closed_mesh(vertices: tuple[Vec, ...], triangles: tuple[Tri, ...]):
    edge_use = {}
    for tid, tri in enumerate(triangles):
        if len(set(tri)) != 3:
            raise RuntimeError("degenerate triangle %d" % tid)
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            key = (a, b) if a < b else (b, a)
            edge_use[key] = edge_use.get(key, 0) + 1
    bad = [edge for edge, count in edge_use.items() if count != 2]
    if bad:
        raise RuntimeError("source mesh is not closed/manifold: edges=%d bad_edges=%d sample=%s"
                           % (len(edge_use), len(bad), bad[:8]))
    return len(edge_use)


def benchmark():
    from freecad_cloth.avatar.AvatarModel import AvatarParameters
    from freecad_cloth.avatar.HumanoidMesh import fit_makehuman_mesh, load_makehuman_mesh

    source = load_makehuman_mesh()
    params = AvatarParameters()
    fitted = fit_makehuman_mesh(source, params, arm_weights=None)
    vertices = tuple(fitted.vertices)
    triangles = tuple(fitted.triangles)
    assert len(triangles) == 26756, len(triangles)
    edge_count = validate_closed_mesh(vertices, triangles)

    t0 = perf_counter()
    bvh = TriangleBVH(vertices, triangles)
    build_s = perf_counter() - t0
    points = deterministic_points(vertices, 1022)

    t0 = perf_counter()
    counts = {"inside": 0, "outside": 0, "boundary": 0}
    for p in points:
        counts[bvh.classify(p)] += 1
    classify_once_s = perf_counter() - t0

    t0 = perf_counter()
    inside_samples = [p for p in points if bvh.classify(p) == "inside"][:128]
    corrected = 0
    for p in inside_samples:
        bvh.correct_outward(p, 2.0)
        corrected += 1
    correction_s = perf_counter() - t0

    t0 = perf_counter()
    total_counts = {"inside": 0, "outside": 0, "boundary": 0}
    for _ in range(90):
        for p in points:
            total_counts[bvh.classify(p)] += 1
    workload_s = perf_counter() - t0

    print(
        "CONTAINMENT_BENCH source_triangles=%d source_vertices=%d edges=%d nodes=%d "
        "build_s=%.6f classify_1022_s=%.6f correction_128_s=%.6f "
        "workload_1022x90_s=%.6f counts=%s"
        % (
            len(triangles), len(vertices), edge_count, len(bvh.nodes), build_s,
            classify_once_s, correction_s, workload_s, total_counts,
        ),
        flush=True,
    )
    assert total_counts["inside"] + total_counts["outside"] + total_counts["boundary"] == 1022 * 90
    assert workload_s < 60.0, workload_s


def synthetic_checks():
    for name, maker, inside, outside, boundary in (
        ("cube", cube, (0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        ("concave-L", concave_l_prism, (0.5, 2.0, 0.5), (2.0, 2.0, 0.5), (0.0, 2.0, 0.5)),
    ):
        vertices, triangles = maker()
        bvh = TriangleBVH(vertices, triangles)
        assert bvh.classify(inside) == "inside", name
        assert bvh.classify(outside) == "outside", name
        assert bvh.classify(boundary) == "boundary", name
        corrected, did_correct = bvh.correct_outward(inside, 0.05)
        assert did_correct and bvh.classify(corrected) == "outside", name
        print("CONTAINMENT_SYNTHETIC name=%s status=passed" % name, flush=True)


if __name__ == "__main__":
    synthetic_checks()
    benchmark()
