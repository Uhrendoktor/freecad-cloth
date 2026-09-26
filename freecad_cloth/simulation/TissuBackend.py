"""Optional Tissu C++ XPBD backend.

The reference solver remains the deterministic fallback. Tissu is imported lazily
so installations without the optional wheel keep the existing backend usable.
"""
from copy import deepcopy
from math import sqrt
from typing import Iterable, Sequence, Tuple
import os

from freecad_cloth.avatar.AvatarCollision import CollisionSurface, coarsen_collision_surface
from freecad_cloth.simulation.TissuContainment import get_authored_surface_containment
from freecad_cloth.simulation.ClothBackend import ClothSimulationBackend
from freecad_cloth.simulation.ClothSolver import ClothSystem

_MM = 1000.0
_TISSU_SUBSTEPS_DEFAULT = 1
_TISSU_COLLISION_TRIANGLES_DEFAULT = 0


def _tissu_substeps():
    value = int(os.environ.get("CLOTH_TISSU_SUBSTEPS", str(_TISSU_SUBSTEPS_DEFAULT)))
    if value < 1:
        raise ValueError("CLOTH_TISSU_SUBSTEPS must be >= 1")
    return value


def _tissu_collision_triangle_limit():
    value = int(os.environ.get("CLOTH_TISSU_COLLISION_TRIANGLES", str(_TISSU_COLLISION_TRIANGLES_DEFAULT)))
    if value < 0:
        raise ValueError("CLOTH_TISSU_COLLISION_TRIANGLES must be >= 0")
    return value


def _tissu_authored_containment_enabled():
    return os.environ.get("CLOTH_TISSU_AUTHORED_CONTAINMENT", "0").strip() == "1"


def _build_stitch_components(stitches, particle_count):
    parent = list(range(int(particle_count)))

    def find(index):
        root = index
        while parent[root] != root:
            root = parent[root]
        while parent[index] != index:
            next_index = parent[index]
            parent[index] = root
            index = next_index
        return root

    for left, right in stitches:
        left = int(left)
        right = int(right)
        if not (0 <= left < particle_count and 0 <= right < particle_count):
            raise ValueError("Tissu stitch particle index out of range")
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    groups = {}
    for index in range(particle_count):
        groups.setdefault(find(index), []).append(index)
    return tuple(
        tuple(sorted(indices))
        for indices in groups.values()
        if len(indices) > 1
    )


def _vector_length(vector):
    return sqrt(sum(float(component) ** 2 for component in vector))


def _to_tissu_vector(vector_mm):
    x, y, z = vector_mm
    return (float(x) / _MM, float(z) / _MM, float(y) / _MM)


def _vector_add(left, right):
    return tuple(float(left[index]) + float(right[index]) for index in range(3))


def _vector_sub(left, right):
    return tuple(float(left[index]) - float(right[index]) for index in range(3))


def _vector_dot(left, right):
    return sum(float(left[index]) * float(right[index]) for index in range(3))


def _vector_scale(vector, factor):
    return tuple(float(value) * float(factor) for value in vector)


def _remove_inward_motion(displacement_tissu, outward_normal_mm):
    normal_tissu = _to_tissu_vector(outward_normal_mm)
    normal_length = _vector_length(normal_tissu)
    if normal_length <= 1.0e-12:
        raise RuntimeError("authored containment returned a degenerate outward normal")
    normal_tissu = _vector_scale(normal_tissu, 1.0 / normal_length)
    normal_component = _vector_dot(displacement_tissu, normal_tissu)
    if normal_component >= 0.0:
        return displacement_tissu
    return _vector_sub(
        displacement_tissu,
        _vector_scale(normal_tissu, normal_component),
    )


def _apply_authored_containment_correction(
    sim,
    containment,
    stitch_components=(),
    stitch_edges=(),
    pinned_indices=(),
):
    particles = sim.solver.get_particles()
    particle_count = len(particles)
    positions_mm = [_from_tissu_position(particle.get_position()) for particle in particles]
    inverse_mass = [float(particle.get_inverse_mass()) for particle in particles]
    pinned = {int(index) for index in pinned_indices}

    corrected = 0
    max_correction_mm = 0.0
    corrected_indices = set()
    stitch_edges = {
        tuple(sorted((int(left), int(right))))
        for left, right in stitch_edges
    }

    def apply_rigid_component(component):
        nonlocal corrected, max_correction_mm
        component = tuple(component)
        component_set = set(component)
        if any(index in pinned or inverse_mass[index] <= 0.0 for index in component):
            return

        candidate_deltas = []
        for index in component:
            correction = containment.correction(positions_mm[index])
            if correction is not None:
                target, _normal = correction
                candidate_deltas.append(
                    _vector_sub(target, positions_mm[index])
                )
        if not candidate_deltas:
            return

        mean_delta = tuple(
            sum(delta[axis] for delta in candidate_deltas) / len(candidate_deltas)
            for axis in range(3)
        )
        candidates = sorted(
            (mean_delta, *candidate_deltas),
            key=lambda delta: (
                _vector_length(delta),
                tuple(round(float(value), 12) for value in delta),
            ),
        )

        chosen = None
        for delta in candidates:
            moved_positions = {
                index: _vector_add(positions_mm[index], delta)
                for index in component
            }
            if all(not containment.contains(value) for value in moved_positions.values()):
                chosen = delta
                break
        if chosen is None:
            return

        seam_before = {
            edge: _vector_length(
                _vector_sub(positions_mm[edge[0]], positions_mm[edge[1]])
            )
            for edge in stitch_edges
            if edge[0] in component_set and edge[1] in component_set
        }
        saved_current = {
            index: tuple(float(value) for value in particles[index].get_position())
            for index in component
        }
        saved_old = {
            index: tuple(float(value) for value in particles[index].get_old_position())
            for index in component
        }

        for index in component:
            correction = containment.correction(positions_mm[index])
            if correction is None:
                target = _vector_add(positions_mm[index], chosen)
                _closest_normal = None
            else:
                target, _closest_normal = correction
                target = _vector_add(positions_mm[index], _vector_sub(target, positions_mm[index]))
                target = _vector_add(positions_mm[index], chosen)

            new_position_tissu = tuple(
                float(value) for value in _to_tissu_position(target)
            )
            displacement_tissu = _vector_sub(saved_current[index], saved_old[index])
            if _closest_normal is None:
                normal_for_velocity = (0.0, 0.0, 1.0)
            else:
                normal_for_velocity = _closest_normal
            displacement_tissu = _remove_inward_motion(
                displacement_tissu,
                normal_for_velocity,
            )
            particle = particles[index]
            particle.set_position(new_position_tissu)
            particle.set_old_position(
                _vector_sub(new_position_tissu, displacement_tissu)
            )

        seam_after = {
            edge: _vector_length(
                _vector_sub(
                    _from_tissu_position(particles[edge[0]].get_position()),
                    _from_tissu_position(particles[edge[1]].get_position()),
                )
            )
            for edge in seam_before
        }
        outside_after = all(
            not containment.contains(_from_tissu_position(particles[index].get_position()))
            for index in component
        )
        seam_preserved = all(
            seam_after[edge] <= seam_before[edge] + 1.0e-9
            for edge in seam_before
        )
        finite_after = all(
            all(abs(float(value)) < 1.0e6 for value in particles[index].get_position())
            and all(abs(float(value)) < 1.0e6 for value in particles[index].get_old_position())
            for index in component
        )
        if not outside_after or not seam_preserved or not finite_after:
            for index in component:
                particles[index].set_position(saved_current[index])
                particles[index].set_old_position(saved_old[index])
            return

        displacement = _vector_length(chosen)
        for index in component:
            positions_mm[index] = _vector_add(positions_mm[index], chosen)
            corrected_indices.add(index)
        corrected += len(component)
        max_correction_mm = max(max_correction_mm, displacement)

    for component in stitch_components:
        apply_rigid_component(component)

    stitch_member_indices = {
        index for component in stitch_components for index in component
    }
    for index in range(particle_count):
        if index in corrected_indices or index in stitch_member_indices:
            continue
        if index in pinned or inverse_mass[index] <= 0.0:
            continue
        correction = containment.correction(positions_mm[index])
        if correction is None:
            continue
        target, normal = correction
        saved_current = tuple(float(value) for value in particles[index].get_position())
        saved_old = tuple(float(value) for value in particles[index].get_old_position())
        new_position_tissu = tuple(float(value) for value in _to_tissu_position(target))
        displacement_tissu = _remove_inward_motion(
            _vector_sub(saved_current, saved_old),
            normal,
        )
        particle = particles[index]
        particle.set_position(new_position_tissu)
        particle.set_old_position(
            _vector_sub(new_position_tissu, displacement_tissu)
        )
        outside_after = not containment.contains(_from_tissu_position(particle.get_position()))
        finite_after = (
            all(abs(float(value)) < 1.0e6 for value in particle.get_position())
            and all(abs(float(value)) < 1.0e6 for value in particle.get_old_position())
        )
        if not outside_after or not finite_after:
            particle.set_position(saved_current)
            particle.set_old_position(saved_old)
            continue
        positions_mm[index] = target
        corrected += 1
        corrected_indices.add(index)
        max_correction_mm = max(
            max_correction_mm,
            _vector_length(_vector_sub(target, _from_tissu_position(saved_current))),
        )

    return corrected, max_correction_mm

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
        self._stitch_components = _build_stitch_components(
            self._stitches,
            len(self._initial.particles),
        )
        self._source_collision_surface = collision_surface
        self._authored_containment = None
        self._authored_containment_corrections = 0
        self._authored_containment_max_correction_mm = 0.0
        if (
            _tissu_authored_containment_enabled()
            and collision_mode == "mesh"
            and self._source_collision_surface is not None
        ):
            self._authored_containment = get_authored_surface_containment(self._source_collision_surface)
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
        if self._authored_containment is not None:
            corrected, max_correction_mm = _apply_authored_containment_correction(
                self._sim,
                self._authored_containment,
                stitch_components=self._stitch_components,
                stitch_edges=self._stitches,
                pinned_indices=self._pin_indices,
            )
            self._authored_containment_corrections += corrected
            self._authored_containment_max_correction_mm = max(
                self._authored_containment_max_correction_mm,
                max_correction_mm,
            )
            if corrected:
                print(
                    "cloth-tissu-authored-containment corrected=%d cumulative=%d max_correction_mm=%.3f time=%.4f"
                    % (
                        corrected,
                        self._authored_containment_corrections,
                        self._authored_containment_max_correction_mm,
                        self._time,
                    ),
                    flush=True,
                )
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
