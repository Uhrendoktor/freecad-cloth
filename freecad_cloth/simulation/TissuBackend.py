"""Optional Tissu C++ XPBD backend.

The reference solver remains the deterministic fallback. Tissu is imported lazily
so installations without the optional wheel keep the existing backend usable.
"""
from copy import deepcopy
from typing import Iterable, Sequence, Tuple
import os

from freecad_cloth.avatar.AvatarCollision import CollisionSurface, coarsen_collision_surface
from freecad_cloth.simulation.ClothBackend import ClothSimulationBackend
from freecad_cloth.simulation.ClothSolver import ClothSystem

_MM = 1000.0
_TISSU_SUBSTEPS_DEFAULT = 1
_TISSU_COLLISION_TRIANGLES_DEFAULT = 0
_TISSU_SIGNED_COLLISION_GUARD_DEFAULT = False


def _tissu_substeps():
    value = int(os.environ.get("CLOTH_TISSU_SUBSTEPS", str(_TISSU_SUBSTEPS_DEFAULT)))
    if value < 1:
        raise ValueError("CLOTH_TISSU_SUBSTEPS must be >= 1")
    return value


def _tissu_signed_collision_guard():
    raw = os.environ.get(
        "CLOTH_TISSU_SIGNED_COLLISION_GUARD",
        "1" if _TISSU_SIGNED_COLLISION_GUARD_DEFAULT else "0",
    ).strip().lower()
    if raw not in {"0", "1", "false", "true", "off", "on"}:
        raise ValueError("CLOTH_TISSU_SIGNED_COLLISION_GUARD must be boolean")
    return raw in {"1", "true", "on"}


def _tissu_collision_triangle_limit():
    value = int(os.environ.get("CLOTH_TISSU_COLLISION_TRIANGLES", str(_TISSU_COLLISION_TRIANGLES_DEFAULT)))
    if value < 0:
        raise ValueError("CLOTH_TISSU_COLLISION_TRIANGLES must be >= 0")
    return value


def _to_tissu_position(position):
    x, y, z = position
    return (float(x) / _MM, float(z) / _MM, float(y) / _MM)


def _from_tissu_position(position):
    x, y, z = position
    return (float(x) * _MM, float(z) * _MM, float(y) * _MM)


def _to_tissu_mesh(surface):
    """Convert FreeCAD collision data to Tissu's pybind-friendly containers."""
    import numpy as np

    vertices = [np.asarray(_to_tissu_position(v), dtype=np.float64) for v in surface.vertices]
    triangles = [[int(a), int(c), int(b)] for a, b, c in surface.triangles]
    return vertices, triangles


def _aabb_distance_squared(point, bounds_min, bounds_max):
    import numpy as np

    delta = np.maximum(np.maximum(bounds_min - point, 0.0), point - bounds_max)
    return float(np.dot(delta, delta))


def _closest_point_on_triangle(point, a, b, c):
    import numpy as np

    ab = b - a
    ac = c - a
    ap = point - a
    d1 = float(np.dot(ab, ap))
    d2 = float(np.dot(ac, ap))
    if d1 <= 0.0 and d2 <= 0.0:
        return a.copy()

    bp = point - b
    d3 = float(np.dot(ab, bp))
    d4 = float(np.dot(ac, bp))
    if d3 >= 0.0 and d4 <= d3:
        return b.copy()

    vc = d1 * d4 - d3 * d2
    if vc <= 0.0 and d1 >= 0.0 and d3 <= 0.0:
        v = d1 / (d1 - d3)
        return a + v * ab

    cp = point - c
    d5 = float(np.dot(ab, cp))
    d6 = float(np.dot(ac, cp))
    if d6 >= 0.0 and d5 <= d6:
        return c.copy()

    vb = d5 * d2 - d1 * d6
    if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
        w = d2 / (d2 - d6)
        return a + w * ac

    va = d3 * d6 - d5 * d4
    if va <= 0.0 and (d4 - d3) >= 0.0 and (d5 - d6) >= 0.0:
        w0 = d4 - d3
        w1 = w0 + (d5 - d6)
        w = 0.0 if w1 <= 1e-15 else w0 / w1
        return b + w * (c - b)

    denominator = va + vb + vc
    if abs(denominator) <= 1e-15:
        return a.copy()
    inverse = 1.0 / denominator
    v = vb * inverse
    w = vc * inverse
    return a + ab * v + ac * w


def _build_signed_collision_bvh(surface, leaf_size=8):
    import numpy as np

    mesh_vertices, mesh_triangles = _to_tissu_mesh(surface)
    vertices = np.asarray(mesh_vertices, dtype=np.float64)
    triangle_points = vertices[np.asarray(mesh_triangles, dtype=np.int32)]
    normals = np.cross(
        triangle_points[:, 1] - triangle_points[:, 0],
        triangle_points[:, 2] - triangle_points[:, 0],
    )
    lengths = np.linalg.norm(normals, axis=1)
    valid = lengths > 1e-12
    triangle_points = triangle_points[valid]
    normals = normals[valid]
    lengths = lengths[valid]
    if not len(triangle_points):
        return None

    # Triangle centroids are spatial partition keys only; authored winding is authoritative.
    centroids = triangle_points.mean(axis=1)
    normals /= lengths[:, None]
    bounds_min = triangle_points.min(axis=1)
    bounds_max = triangle_points.max(axis=1)
    triangle_ids = np.arange(len(triangle_points), dtype=np.int32)
    nodes = []

    def build(indices):
        node_id = len(nodes)
        nodes.append(None)
        node_min = bounds_min[indices].min(axis=0)
        node_max = bounds_max[indices].max(axis=0)
        if len(indices) <= leaf_size:
            nodes[node_id] = (node_min, node_max, -1, -1, indices)
            return node_id
        axis = int(np.argmax(node_max - node_min))
        order = indices[np.argsort(centroids[indices, axis], kind="mergesort")]
        middle = len(order) // 2
        left = build(order[:middle])
        right = build(order[middle:])
        nodes[node_id] = (node_min, node_max, left, right, None)
        return node_id

    root = build(triangle_ids)
    return {
        "triangles": triangle_points,
        "normals": normals,
        "nodes": nodes,
        "root": root,
    }


def _nearest_signed_collision(bvh, point):
    import heapq
    import numpy as np

    if bvh is None:
        return None
    heap = []
    root = bvh["root"]
    root_data = bvh["nodes"][root]
    heapq.heappush(heap, (_aabb_distance_squared(point, root_data[0], root_data[1]), root))
    best_distance = float("inf")
    best_point = None
    best_index = -1

    while heap:
        bound_distance, node_id = heapq.heappop(heap)
        if bound_distance >= best_distance:
            continue
        _, _, left, right, indices = bvh["nodes"][node_id]
        if left < 0:
            for index in indices:
                triangle = bvh["triangles"][int(index)]
                closest = _closest_point_on_triangle(point, triangle[0], triangle[1], triangle[2])
                delta = point - closest
                distance_squared = float(np.dot(delta, delta))
                if distance_squared < best_distance:
                    best_distance = distance_squared
                    best_point = closest
                    best_index = int(index)
            continue
        for child in (left, right):
            child_min, child_max = bvh["nodes"][child][0], bvh["nodes"][child][1]
            child_distance = _aabb_distance_squared(point, child_min, child_max)
            if child_distance < best_distance:
                heapq.heappush(heap, (child_distance, child))

    if best_index < 0 or best_point is None:
        return None
    return best_point, bvh["normals"][best_index], best_distance ** 0.5


def _signed_collision_guard_correction(position, old_position, closest, normal, thickness):
    import numpy as np

    signed_distance = float(np.dot(position - closest, normal))
    if signed_distance >= 0.0:
        return None
    corrected = closest + normal * float(thickness)
    displacement = position - old_position
    normal_velocity = float(np.dot(displacement, normal))
    if normal_velocity < 0.0:
        displacement = displacement - normal_velocity * normal
    corrected_old = corrected - displacement
    return corrected, corrected_old, -signed_distance


def _collision_envelope(surface):
    """Derive a stable torso envelope from the authored avatar collision data."""
    if surface is None or not surface.vertices:
        return ()
    xs = [float(v[0]) for v in surface.vertices]
    ys = [float(v[1]) for v in surface.vertices]
    zs = [float(v[2]) for v in surface.vertices]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    min_z, max_z = min(zs), max(zs)
    height = max(1.0, max_z - min_z)
    width = max(1.0, max_x - min_x)
    depth = max(1.0, max_y - min_y)
    center_x = 0.5 * (min_x + max_x)
    center_y = 0.5 * (min_y + max_y)

    radius = max(120.0, min(240.0, 0.245 * width, 0.70 * depth))
    bottom = min_z + 0.38 * height
    top = min_z + 0.76 * height
    samples = (0.0, 0.25, 0.50, 0.75, 1.0)
    return tuple(
        (
            (center_x, center_y, bottom + (top - bottom) * t),
            radius,
        )
        for t in samples
    )


class TissuBackend(ClothSimulationBackend):
    """C++ XPBD backend with selectable Tissu collision paths."""

    name = "tissu"

    def __init__(
        self,
        system: ClothSystem,
        triangles: Sequence[Tuple[int, int, int]],
        pins: Iterable[int] = (),
        stitches: Iterable[Tuple[int, int]] = (),
        collision_surface: CollisionSurface | None = None,
        collision_mode: str = "torso-envelope",
    ):
        try:
            from tissu import Simulation
        except ImportError as exc:
            raise RuntimeError("Tissu backend requires the optional 'pytissu' package") from exc
        collision_mode = str(os.environ.get("CLOTH_TISSU_COLLISION_MODE", collision_mode)).strip().lower()
        if collision_mode not in {"mesh", "torso-envelope"}:
            raise ValueError("unsupported Tissu collision mode")
        self._initial = deepcopy(system)
        self._triangles = tuple(tuple(int(i) for i in tri) for tri in triangles)
        self._pin_indices = tuple(dict.fromkeys(int(i) for i in pins))
        self._stitches = tuple((int(a), int(b)) for a, b in stitches)
        self._source_collision_surface = collision_surface
        self._signed_collision_guard = _tissu_signed_collision_guard()
        collision_limit = _tissu_collision_triangle_limit()
        if collision_surface is not None and collision_mode == "mesh" and collision_limit:
            collision_surface = coarsen_collision_surface(collision_surface, collision_limit)
            print(
                "cloth-tissu-collision source_triangles=%d solver_triangles=%d limit=%d"
                % (
                    len(self._source_collision_surface.triangles),
                    len(collision_surface.triangles),
                    collision_limit,
                ),
                flush=True,
            )
        self._collision_surface = collision_surface
        self._collision_mode = collision_mode
        self._signed_collision_bvh = (
            _build_signed_collision_bvh(self._collision_surface)
            if self._signed_collision_guard
            and self._collision_mode == "mesh"
            and self._collision_surface is not None
            else None
        )
        self._signed_guard_corrections = 0
        self._signed_guard_max_penetration = 0.0
        self._time = 0.0
        self._iterations = 8
        self._substeps = _tissu_substeps()
        self._build(Simulation)

    @property
    def solver_collision_surface(self):
        """Return the exact surface registered with Tissu's solver."""
        return self._collision_surface

    @property
    def time(self):
        return self._time

    def _add_collision(self):
        import numpy as np
        if self._collision_surface is None:
            return
        if self._collision_mode == "torso-envelope":
            for index, (center, radius_mm) in enumerate(_collision_envelope(self._collision_surface)):
                self._sim.add_sphere(
                    f"drape-torso-{index}",
                    np.asarray(_to_tissu_position(center), dtype=np.float64),
                    float(radius_mm) / _MM,
                    friction=0.5,
                )
            return
        vtx, idx = _to_tissu_mesh(self._collision_surface)
        self._sim.add_mesh_from_arrays("drape-target", vtx, idx, friction=0.5)

    def _build(self, Simulation):
        import numpy as np
        positions = [_to_tissu_position(p.position()) for p in self._initial.particles]
        triangles = np.asarray(self._triangles, dtype=np.int32)
        vertices = np.asarray(positions, dtype=np.float64)
        self._sim = Simulation(substeps=self._substeps, iterations=self._iterations, gravity=-9.81, thickness=0.002)
        self._fabric = self._sim.create_from_arrays("cloth", vertices, triangles, material="cotton")
        global_ids = np.asarray(self._fabric.instance.get_particle_indices(), dtype=np.int32)
        if len(global_ids) != len(positions) or not np.array_equal(global_ids, np.arange(len(positions))):
            raise RuntimeError("Tissu did not preserve cloth particle ordering")
        for index in self._pin_indices:
            self._sim.solver.add_pin(int(index), np.asarray(positions[index], dtype=np.float64), 0.0)
        for a, b in self._stitches:
            self._sim.solver.add_stitch(int(a), int(b), 0.0)
        self._add_collision()

    def _apply_signed_collision_guard(self):
        import numpy as np

        if self._signed_collision_bvh is None:
            return 0
        thickness = float(getattr(self._sim, "thickness", 0.002))
        corrected_count = 0
        max_penetration = 0.0
        for particle in self._sim.solver.get_particles():
            if float(particle.get_inverse_mass()) <= 0.0:
                continue
            position = np.asarray(particle.get_position(), dtype=np.float64)
            nearest = _nearest_signed_collision(self._signed_collision_bvh, position)
            if nearest is None:
                continue
            closest, normal, _distance = nearest
            correction = _signed_collision_guard_correction(
                position,
                np.asarray(particle.get_old_position(), dtype=np.float64),
                closest,
                normal,
                thickness,
            )
            if correction is None:
                continue
            corrected, corrected_old, penetration = correction
            particle.set_position(corrected)
            particle.set_old_position(corrected_old)
            corrected_count += 1
            max_penetration = max(max_penetration, float(penetration))
        if corrected_count:
            self._signed_guard_corrections += corrected_count
            self._signed_guard_max_penetration = max(self._signed_guard_max_penetration, max_penetration)
            print(
                "cloth-tissu-signed-guard corrections=%d cumulative=%d max_penetration_mm=%.3f"
                % (
                    corrected_count,
                    self._signed_guard_corrections,
                    self._signed_guard_max_penetration * _MM,
                ),
                flush=True,
            )
        return corrected_count


    def step(self, dt=1.0 / 60.0, iterations=8, gravity=(0.0, 0.0, -9810.0), sphere=None, surface=None):
        if dt <= 0 or iterations < 1:
            raise ValueError("dt and iterations must be positive")
        if surface is not None and surface is not self._collision_surface:
            raise RuntimeError("TissuBackend collision surface is immutable after construction")
        if sphere is not None:
            raise RuntimeError("TissuBackend does not support sphere fallback collision")
        self._sim.solver.set_iterations(max(1, int(iterations)))
        _gx, _gy, gz = gravity
        self._sim.gravity = float(gz) / _MM
        self._sim.step(float(dt))
        if self._signed_collision_guard:
            self._apply_signed_collision_guard()
        self._iterations = int(iterations)
        self._time += float(dt)

    def reset(self):
        from tissu import Simulation
        self._time = 0.0
        self._build(Simulation)

    def pin(self, indices: Iterable[int]):
        import numpy as np
        self._pin_indices = tuple(dict.fromkeys(int(i) for i in indices))
        for index in self._pin_indices:
            position = self.positions()[index]
            self._sim.solver.add_pin(int(index), np.asarray(_to_tissu_position(position), dtype=np.float64), 0.0)

    def set_stitches(self, pairs: Iterable[Tuple[int, int]], compliance=0.0):
        self._stitches = tuple((int(a), int(b)) for a, b in pairs)
        for a, b in self._stitches:
            self._sim.solver.add_stitch(int(a), int(b), float(compliance))

    def positions(self):
        return tuple(_from_tissu_position(p) for p in self._sim.positions)

    def finite(self):
        return all(abs(v) < 1e12 for p in self.positions() for v in p)
