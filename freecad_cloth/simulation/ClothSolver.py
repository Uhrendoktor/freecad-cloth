"""Small deterministic XPBD-style reference solver for garment panels.

The backend is intentionally FreeCAD-independent. Positions are millimetres,
velocities millimetres/second and gravity millimetres/second².
"""
from dataclasses import dataclass
from itertools import combinations
from math import floor, sqrt


@dataclass
class Particle:
    x: float
    y: float
    z: float
    inv_mass: float = 1.0
    px: float = 0.0
    py: float = 0.0
    pz: float = 0.0

    def position(self):
        return (self.x, self.y, self.z)


@dataclass(frozen=True)
class DistanceConstraint:
    a: int
    b: int
    rest: float
    compliance: float = 0.0


def distance(a, b):
    return sqrt((a.x-b.x)**2 + (a.y-b.y)**2 + (a.z-b.z)**2)


def _closest_point_triangle(p, a, b, c):
    """Return the closest point on triangle ABC to point P."""
    ab = tuple(b[i] - a[i] for i in range(3))
    ac = tuple(c[i] - a[i] for i in range(3))
    ap = tuple(p[i] - a[i] for i in range(3))
    d1 = sum(ab[i] * ap[i] for i in range(3))
    d2 = sum(ac[i] * ap[i] for i in range(3))
    if d1 <= 0.0 and d2 <= 0.0:
        return a
    bp = tuple(p[i] - b[i] for i in range(3))
    d3 = sum(ab[i] * bp[i] for i in range(3))
    d4 = sum(ac[i] * bp[i] for i in range(3))
    if d3 >= 0.0 and d4 <= d3:
        return b
    vc = d1 * d4 - d3 * d2
    if vc <= 0.0 and d1 >= 0.0 and d3 <= 0.0:
        v = d1 / (d1 - d3)
        return tuple(a[i] + v * ab[i] for i in range(3))
    cp = tuple(p[i] - c[i] for i in range(3))
    d5 = sum(ab[i] * cp[i] for i in range(3))
    d6 = sum(ac[i] * cp[i] for i in range(3))
    if d6 >= 0.0 and d5 <= d6:
        return c
    vb = d5 * d2 - d1 * d6
    if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
        w = d2 / (d2 - d6)
        return tuple(a[i] + w * ac[i] for i in range(3))
    va = d3 * d6 - d5 * d4
    if va <= 0.0 and (d4 - d3) >= 0.0 and (d5 - d6) >= 0.0:
        w = (d4 - d3) / ((d4 - d3) + (d5 - d6))
        return tuple(b[i] + w * (c[i] - b[i]) for i in range(3))
    denom = 1.0 / (va + vb + vc)
    v = vb * denom
    w = vc * denom
    return tuple(a[i] + ab[i] * v + ac[i] * w for i in range(3))


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _normalize(v):
    length = sqrt(sum(c * c for c in v))
    if length < 1e-12:
        return None
    return tuple(c / length for c in v)


def _solve_linear_system(matrix, rhs):
    """Solve a tiny dense linear system with partial pivoting."""
    size = len(rhs)
    rows = [list(matrix[i]) + [float(rhs[i])] for i in range(size)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(rows[row][column]))
        if abs(rows[pivot][column]) < 1e-10:
            return None
        if pivot != column:
            rows[column], rows[pivot] = rows[pivot], rows[column]
        pivot_value = rows[column][column]
        for row in range(column + 1, size):
            factor = rows[row][column] / pivot_value
            if factor == 0.0:
                continue
            for col in range(column, size + 1):
                rows[row][col] -= factor * rows[column][col]
    solution = [0.0] * size
    for row in range(size - 1, -1, -1):
        remainder = rows[row][-1] - sum(rows[row][col] * solution[col] for col in range(row + 1, size))
        solution[row] = remainder / rows[row][row]
    return tuple(solution)


def _minimal_mesh_correction(position, constraints):
    """Return the minimum-norm correction satisfying local mesh half-spaces."""
    best = None
    count = len(constraints)
    for active_size in range(1, min(3, count) + 1):
        for active in combinations(range(count), active_size):
            normals = [constraints[index][0] for index in active]
            rhs = [
                constraints[index][1] - sum(normals[row_component][component] * position[component]
                                            for component in range(3))
                for row_component in range(active_size)
            ]
            matrix = [
                [
                    sum(normals[row][component] * normals[column][component] for component in range(3))
                    for column in range(active_size)
                ]
                for row in range(active_size)
            ]
            multipliers = _solve_linear_system(matrix, rhs)
            if multipliers is None or any(value < -1e-9 for value in multipliers):
                continue
            multipliers = tuple(0.0 if abs(value) < 1e-9 else value for value in multipliers)
            correction = [0.0, 0.0, 0.0]
            for multiplier, normal in zip(multipliers, normals):
                for component in range(3):
                    correction[component] += multiplier * normal[component]
            if any(
                sum(normal[component] * (position[component] + correction[component]) for component in range(3))
                < target - 1e-8
                for normal, target in constraints
            ):
                continue
            norm_sq = sum(value * value for value in correction)
            tie_key = tuple(active)
            candidate = (norm_sq, tie_key, tuple(correction))
            if best is None or candidate[:2] < best[:2]:
                best = candidate
    return None if best is None else best[2]


class ClothSystem:
    def __init__(self, particles, constraints=(), stitches=(), pins=()):
        self.particles = list(particles)
        self.constraints = list(constraints)
        self.stitches = list(stitches)
        self.pins = {int(i): tuple(p) for i, p in pins}
        self.time = 0.0
        self._surface_cache = {}

    @classmethod
    def grid(cls, width, height, nx=8, ny=5, origin=(0.0, 0.0, 0.0)):
        ox, oy, oz = origin
        particles = []
        for j in range(ny):
            for i in range(nx):
                x = ox + width * i / (nx - 1)
                y = oy + height * j / (ny - 1)
                particles.append(Particle(x, y, oz, 1.0))
        constraints = []
        def idx(i, j): return j * nx + i
        for j in range(ny):
            for i in range(nx):
                if i + 1 < nx:
                    a, b = particles[idx(i,j)], particles[idx(i+1,j)]
                    constraints.append(DistanceConstraint(idx(i,j), idx(i+1,j), distance(a,b)))
                if j + 1 < ny:
                    a, b = particles[idx(i,j)], particles[idx(i,j+1)]
                    constraints.append(DistanceConstraint(idx(i,j), idx(i,j+1), distance(a,b)))
                if i + 1 < nx and j + 1 < ny:
                    a, b = particles[idx(i,j)], particles[idx(i+1,j+1)]
                    constraints.append(DistanceConstraint(idx(i,j), idx(i+1,j+1), distance(a,b)))
                    a, b = particles[idx(i+1,j)], particles[idx(i,j+1)]
                    constraints.append(DistanceConstraint(idx(i+1,j), idx(i,j+1), distance(a,b)))
        return cls(particles, constraints)

    def step(self, dt=1.0/60.0, iterations=8, gravity=(0.0, 0.0, -9810.0), sphere=None, surface=None):
        if dt <= 0 or iterations < 1:
            raise ValueError("dt and iterations must be positive")
        gx, gy, gz = gravity
        if self.time == 0.0:
            for p in self.particles:
                p.px, p.py, p.pz = p.x, p.y, p.z
        old = [(p.x, p.y, p.z) for p in self.particles]
        for i, p in enumerate(self.particles):
            if p.inv_mass == 0.0 or i in self.pins:
                continue
            p.x += (p.x - p.px) + gx * dt * dt
            p.y += (p.y - p.py) + gy * dt * dt
            p.z += (p.z - p.pz) + gz * dt * dt
        for i, p in enumerate(self.particles):
            p.px, p.py, p.pz = old[i]
        for _ in range(iterations):
            for c in self.constraints + self.stitches:
                self._project(c)
            if surface is not None:
                self._collide_surface(surface)
            elif sphere is not None:
                self._collide_sphere(*sphere)
            for i, pos in self.pins.items():
                p = self.particles[i]
                p.x, p.y, p.z = pos
        self.time += dt

    def _project(self, c):
        a, b = self.particles[c.a], self.particles[c.b]
        dx, dy, dz = b.x-a.x, b.y-a.y, b.z-a.z
        length = sqrt(dx*dx + dy*dy + dz*dz)
        if length < 1e-12:
            return
        w = a.inv_mass + b.inv_mass
        if w <= 0:
            return
        correction = (length - c.rest) / length / w
        if a.inv_mass:
            a.x += dx * correction * a.inv_mass
            a.y += dy * correction * a.inv_mass
            a.z += dz * correction * a.inv_mass
        if b.inv_mass:
            b.x -= dx * correction * b.inv_mass
            b.y -= dy * correction * b.inv_mass
            b.z -= dz * correction * b.inv_mass

    def _prepare_surface(self, surface):
        cached = self._surface_cache.get(id(surface))
        if cached is not None:
            return cached
        surface.validate()
        center = surface.center
        cell_size = max(50.0, min(120.0, 4.0 * max(float(surface.thickness), 1.0)))
        prepared = []
        grid = {}

        def cell_coord(point):
            return tuple(int(floor(float(point[i]) / cell_size)) for i in range(3))

        for triangle_index, (ia, ib, ic) in enumerate(surface.triangles):
            a, b, c = surface.vertices[ia], surface.vertices[ib], surface.vertices[ic]
            normal = _normalize(_cross(tuple(b[i] - a[i] for i in range(3)), tuple(c[i] - a[i] for i in range(3))))
            if normal is None:
                continue
            face_center = tuple((a[i] + b[i] + c[i]) / 3.0 for i in range(3))
            if sum(normal[i] * (center[i] - face_center[i]) for i in range(3)) > 0.0:
                normal = tuple(-value for value in normal)
            prepared.append((a, b, c, normal))
            mins = tuple(min(a[i], b[i], c[i]) - surface.thickness for i in range(3))
            maxs = tuple(max(a[i], b[i], c[i]) + surface.thickness for i in range(3))
            lo = cell_coord(mins)
            hi = cell_coord(maxs)
            prepared_index = len(prepared) - 1
            for ix in range(lo[0], hi[0] + 1):
                for iy in range(lo[1], hi[1] + 1):
                    for iz in range(lo[2], hi[2] + 1):
                        grid.setdefault((ix, iy, iz), []).append(prepared_index)

        cached = (cell_size, prepared, grid)
        self._surface_cache[id(surface)] = cached
        return cached

    def _collide_surface(self, surface):
        cell_size, prepared, grid = self._prepare_surface(surface)
        thickness = float(surface.thickness)
        for p in self.particles:
            if p.inv_mass == 0.0 or not prepared:
                continue
            position = p.position()
            low = tuple(int(floor((position[i] - thickness) / cell_size)) for i in range(3))
            high = tuple(int(floor((position[i] + thickness) / cell_size)) for i in range(3))
            candidate_ids = set()
            for ix in range(low[0], high[0] + 1):
                for iy in range(low[1], high[1] + 1):
                    for iz in range(low[2], high[2] + 1):
                        candidate_ids.update(grid.get((ix, iy, iz), ()))
            if not candidate_ids:
                continue

            candidates = []
            nearest_surface_distance_sq = None
            for triangle_index in sorted(candidate_ids):
                a, b, c, normal = prepared[triangle_index]
                closest = _closest_point_triangle(position, a, b, c)
                delta = tuple(position[i] - closest[i] for i in range(3))
                distance_sq = sum(d * d for d in delta)
                if nearest_surface_distance_sq is None or distance_sq < nearest_surface_distance_sq:
                    nearest_surface_distance_sq = distance_sq
                signed = sum(delta[i] * normal[i] for i in range(3))
                correction = thickness - signed
                if correction <= 0.0:
                    continue
                plane_offset = sum(normal[i] * a[i] for i in range(3))
                candidates.append(
                    (distance_sq, triangle_index, normal, plane_offset + thickness, correction)
                )
            if not candidates:
                continue

            candidates.sort(key=lambda item: (item[0], item[1]))
            best = candidates[0]
            local_distance_limit = nearest_surface_distance_sq + max(thickness * thickness, 1e-12)
            local_correction_limit = best[4] + max(thickness, 1e-6)
            local = []
            for candidate in candidates:
                if candidate[0] > local_distance_limit or candidate[4] > local_correction_limit:
                    continue
                _, triangle_index, normal, target, _ = candidate
                duplicate = False
                for existing_index, existing in enumerate(local):
                    if sum(normal[i] * existing[0][i] for i in range(3)) > 1.0 - 1e-10:
                        if target > existing[1]:
                            local[existing_index] = (normal, target, triangle_index)
                        duplicate = True
                        break
                if not duplicate:
                    local.append((normal, target, triangle_index))
            local.sort(key=lambda item: item[2])
            local = local[:8]

            constraints = [(normal, target) for normal, target, _ in local]
            correction_vector = _minimal_mesh_correction(position, constraints)
            if correction_vector is None:
                _, _, normal, _, correction = best
                correction_vector = tuple(normal[i] * correction for i in range(3))
            p.x += correction_vector[0]
            p.y += correction_vector[1]
            p.z += correction_vector[2]

    def _collide_sphere(self, cx, cy, cz, radius):
        for p in self.particles:
            if p.inv_mass == 0.0:
                continue
            dx, dy, dz = p.x-cx, p.y-cy, p.z-cz
            d = sqrt(dx*dx + dy*dy + dz*dz)
            if 0.0 < d < radius:
                s = radius/d
                p.x, p.y, p.z = cx+dx*s, cy+dy*s, cz+dz*s

    def add_stitches(self, pairs, compliance=0.0):
        """Add zero-rest-length sewing constraints between corresponding edge samples."""
        for a, b in pairs:
            self.stitches.append(DistanceConstraint(int(a), int(b), 0.0, compliance))

    def pin(self, indices):
        for i in indices:
            self.pins[int(i)] = self.particles[int(i)].position()
            self.particles[int(i)].inv_mass = 0.0

    def finite(self):
        return all(abs(v) < 1e12 for p in self.particles for v in p.position())
