"""Small deterministic XPBD-style reference solver for garment panels.

The backend is intentionally FreeCAD-independent. Positions are millimetres,
velocities millimetres/second and gravity millimetres/second².
"""
from dataclasses import dataclass
from math import sqrt


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


class ClothSystem:
    def __init__(self, particles, constraints=(), stitches=(), pins=()):
        self.particles = list(particles)
        self.constraints = list(constraints)
        self.stitches = list(stitches)
        self.pins = {int(i): tuple(p) for i, p in pins}
        self.time = 0.0

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

    def step(self, dt=1.0/60.0, iterations=8, gravity=(0.0, 0.0, -9810.0), sphere=None):
        if dt <= 0 or iterations < 1:
            raise ValueError("dt and iterations must be positive")
        gx, gy, gz = gravity
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
            if sphere is not None:
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
        for a, b in pairs:
            pa, pb = self.particles[a], self.particles[b]
            self.stitches.append(DistanceConstraint(a, b, distance(pa, pb), compliance))

    def pin(self, indices):
        for i in indices:
            self.pins[int(i)] = self.particles[int(i)].position()
            self.particles[int(i)].inv_mass = 0.0

    def finite(self):
        return all(abs(v) < 1e12 for p in self.particles for v in p.position())
