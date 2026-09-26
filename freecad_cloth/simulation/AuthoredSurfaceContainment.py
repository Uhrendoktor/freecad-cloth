"""Closed authored-mesh containment and outward correction."""
from math import sqrt
from time import perf_counter
from freecad_cloth.avatar.AvatarCollision import CollisionSurface

_RAY = (1.0, 0.0, 0.0)
_EPS = 1.0e-9

def _sub(a, b):
    return tuple(float(a[i]) - float(b[i]) for i in range(3))

def _dot(a, b):
    return sum(float(a[i]) * float(b[i]) for i in range(3))

def _cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])

def _norm(v):
    length = sqrt(_dot(v, v))
    if length <= _EPS:
        return None
    return tuple(float(c) / length for c in v)

def _signed_volume(vertices, triangles):
    total = 0.0
    for ia, ib, ic in triangles:
        total += _dot(vertices[ia], _cross(vertices[ib], vertices[ic]))
    return total / 6.0

def _closed_winding(surface):
    edges = {}
    for ia, ib, ic in surface.triangles:
        for a, b in ((ia, ib), (ib, ic), (ic, ia)):
            key = (min(int(a), int(b)), max(int(a), int(b)))
            sign = 1 if int(a) < int(b) else -1
            count, winding = edges.get(key, (0, 0))
            edges[key] = count + 1, winding + sign
    return bool(edges) and all(count == 2 and winding == 0 for count, winding in edges.values())

class AuthoredSurfaceContainment:
    def __init__(self, surface, cell_size=50.0):
        if not isinstance(surface, CollisionSurface):
            raise TypeError("surface must be a CollisionSurface")
        surface.validate()
        if not _closed_winding(surface):
            raise ValueError("authored collision surface must be closed and consistently oriented")
        xs = [float(v[0]) for v in surface.vertices]
        ys = [float(v[1]) for v in surface.vertices]
        zs = [float(v[2]) for v in surface.vertices]
        self.surface = surface
        self.cell_size = max(5.0, float(cell_size))
        dx, dy, dz = max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs)
        diagonal = sqrt(dx*dx + dy*dy + dz*dz)
        self._boundary_eps = max(1.0e-5, diagonal * 1.0e-9)
        self._jitter = max(1.0e-5, diagonal * 1.0e-8)
        volume = _signed_volume(surface.vertices, surface.triangles)
        if abs(volume) <= max(1.0, diagonal**3) * 1.0e-12:
            raise ValueError("authored collision surface has indeterminate winding")
        self._outward_sign = 1.0 if volume > 0.0 else -1.0
        self._correction_thickness = max(2.0, float(surface.thickness))
        self._triangles = []
        self._grid = {}
        for ia, ib, ic in surface.triangles:
            a = tuple(float(v) for v in surface.vertices[ia])
            b = tuple(float(v) for v in surface.vertices[ib])
            c = tuple(float(v) for v in surface.vertices[ic])
            normal = _norm(_cross(_sub(b, a), _sub(c, a)))
            if normal is None:
                continue
            if self._outward_sign < 0.0:
                normal = tuple(-v for v in normal)
            index = len(self._triangles)
            self._triangles.append((a, b, c, normal))
            lo_y, hi_y = int(min(a[1],b[1],c[1]) // self.cell_size), int(max(a[1],b[1],c[1]) // self.cell_size)
            lo_z, hi_z = int(min(a[2],b[2],c[2]) // self.cell_size), int(max(a[2],b[2],c[2]) // self.cell_size)
            for iy in range(lo_y, hi_y + 1):
                for iz in range(lo_z, hi_z + 1):
                    self._grid.setdefault((iy, iz), []).append(index)
        if not self._triangles:
            raise ValueError("authored collision surface has no usable triangles")

    def _hits(self, point):
        candidates = self._grid.get((int(point[1] // self.cell_size), int(point[2] // self.cell_size)), ())
        hits = []
        ambiguous = False
        for index in candidates:
            a, b, c, _ = self._triangles[index]
            e1, e2 = _sub(b, a), _sub(c, a)
            pvec = _cross(_RAY, e2)
            det = _dot(e1, pvec)
            if abs(det) <= _EPS:
                continue
            inv = 1.0 / det
            tvec = _sub(point, a)
            u = _dot(tvec, pvec) * inv
            if u < -1.0e-10 or u > 1.0 + 1.0e-10:
                continue
            qvec = _cross(tvec, e1)
            v = _dot(_RAY, qvec) * inv
            if v < -1.0e-10 or u + v > 1.0 + 1.0e-10:
                continue
            t = _dot(e2, qvec) * inv
            if t <= self._boundary_eps:
                continue
            if u <= 1.0e-8 or v <= 1.0e-8 or u + v >= 1.0 - 1.0e-8:
                ambiguous = True
            hits.append((t, index))
        hits.sort(key=lambda item: (item[0], item[1]))
        unique = []
        t_eps = max(4.0 * self._boundary_eps, 1.0e-5)
        for hit in hits:
            if unique and abs(hit[0] - unique[-1][0]) <= t_eps:
                continue
            unique.append(hit)
        return unique, ambiguous

    def _parity(self, point, dy=0.0, dz=0.0):
        probe = (float(point[0]), float(point[1]) + dy, float(point[2]) + dz)
        hits, ambiguous = self._hits(probe)
        return bool(len(hits) % 2), hits, ambiguous

    def classify(self, point):
        inside, hits, ambiguous = self._parity(point)
        if not ambiguous:
            return ("inside" if inside else "outside", hits)
        a, hits_a, _ = self._parity(point, self._jitter, 2.0 * self._jitter)
        b, hits_b, _ = self._parity(point, -2.0 * self._jitter, self._jitter)
        votes = int(inside) + int(a) + int(b)
        if votes == 3:
            return "inside", hits_a or hits_b or hits
        if votes == 0:
            return "outside", hits_a or hits_b or hits
        return "outside", ()

    def correct(self, point):
        state, hits = self.classify(point)
        if state != "inside" or not hits:
            return None
        t, index = hits[0]
        normal = self._triangles[index][3]
        exit_point = (float(point[0]) + t, float(point[1]), float(point[2]))
        thickness = self._correction_thickness
        corrected = tuple(exit_point[i] + normal[i] * thickness for i in range(3))
        return corrected, float(t), normal

    def benchmark(self, points, iterations):
        started = perf_counter()
        inside = outside = 0
        for _ in range(int(iterations)):
            for point in points:
                state, _ = self.classify(point)
                if state == "inside":
                    inside += 1
                else:
                    outside += 1
        elapsed = perf_counter() - started
        return {"points": len(points), "iterations": int(iterations), "queries": len(points) * int(iterations), "elapsed_s": elapsed, "inside": inside, "outside": outside}
