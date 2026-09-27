"""Optional Tissu C++ XPBD backend.

The reference solver remains the deterministic fallback. Tissu is imported lazily
so installations without the optional wheel keep the existing backend usable.
"""
from copy import deepcopy
from typing import Iterable, Sequence, Tuple
import os
from math import isfinite

from freecad_cloth.avatar.AvatarCollision import CollisionSurface, surface_from_triangles
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


def _mesh_topology_metrics(vertices, triangles):
    """Return deterministic topology metrics for a solver-facing collision mesh."""
    vertices = tuple(tuple(float(c) for c in point) for point in vertices)
    triangles = tuple(tuple(int(i) for i in tri) for tri in triangles)
    if len(vertices) < 3 or not triangles:
        raise ValueError("collision mesh is empty")
    if any(not isfinite(float(coordinate)) for point in vertices for coordinate in point):
        raise ValueError("collision mesh contains non-finite vertices")
    edge_faces = {}
    adjacency = [set() for _ in triangles]
    degenerate = 0
    for face_index, (a, b, c) in enumerate(triangles):
        if len({a, b, c}) != 3:
            degenerate += 1
            continue
        if any(index < 0 or index >= len(vertices) for index in (a, b, c)):
            raise ValueError("collision mesh triangle index out of range")
        for left, right in ((a, b), (b, c), (c, a)):
            edge = (min(left, right), max(left, right))
            edge_faces.setdefault(edge, []).append(face_index)
    for faces in edge_faces.values():
        if len(faces) > 1:
            for face_index in faces:
                adjacency[face_index].update(other for other in faces if other != face_index)
    visited = set()
    components = 0
    for face_index in range(len(triangles)):
        if face_index in visited:
            continue
        components += 1
        stack = [face_index]
        visited.add(face_index)
        while stack:
            current = stack.pop()
            for neighbor in adjacency[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)
    return {
        "vertices": len(vertices),
        "faces": len(triangles),
        "components": components,
        "boundary_edges": sum(1 for faces in edge_faces.values() if len(faces) == 1),
        "nonmanifold_edges": sum(1 for faces in edge_faces.values() if len(faces) > 2),
        "degenerate_faces": degenerate,
    }


def _native_decimate_collision_surface(surface, max_triangles):
    """Use FreeCAD's native mesh decimator without changing the model ABI."""
    limit = int(max_triangles)
    surface.validate()
    if limit < 1:
        raise ValueError("max_triangles must be positive")
    if len(surface.triangles) <= limit:
        return surface, _mesh_topology_metrics(surface.vertices, surface.triangles), 0.0

    source_metrics = _mesh_topology_metrics(surface.vertices, surface.triangles)
    if source_metrics["degenerate_faces"]:
        raise RuntimeError("native collision decimation source contains degenerate faces")
    if source_metrics["nonmanifold_edges"]:
        raise RuntimeError("native collision decimation source is non-manifold")

    try:
        import FreeCAD as App
        import Mesh
    except ImportError as exc:
        raise RuntimeError("FreeCAD Mesh runtime is required for native collision decimation") from exc

    from time import perf_counter
    started = perf_counter()
    native = Mesh.Mesh()
    vectors = [App.Vector(*point) for point in surface.vertices]
    native.addFacets([(vectors[a], vectors[b], vectors[c]) for a, b, c in surface.triangles])
    native.decimate(limit)
    raw_vertices, raw_triangles = native.Topology
    vertices = tuple((float(vertex.x), float(vertex.y), float(vertex.z)) for vertex in raw_vertices)
    triangles = tuple(tuple(int(i) for i in face) for face in raw_triangles)
    metrics = _mesh_topology_metrics(vertices, triangles)
    if metrics["faces"] != limit:
        raise RuntimeError(
            "native collision decimation produced %d faces; expected %d"
            % (metrics["faces"], limit)
        )
    if metrics["degenerate_faces"] or metrics["nonmanifold_edges"]:
        raise RuntimeError(
            "native collision decimation produced invalid topology: %s" % metrics
        )
    if metrics["components"] != source_metrics["components"]:
        raise RuntimeError(
            "native collision decimation changed component count: %d -> %d"
            % (source_metrics["components"], metrics["components"])
        )
    if source_metrics["boundary_edges"] == 0 and metrics["boundary_edges"] != 0:
        raise RuntimeError(
            "native collision decimation opened a closed source surface: boundary_edges=%d"
            % metrics["boundary_edges"]
        )
    result = surface_from_triangles(vertices, triangles, surface.region, surface.thickness)
    elapsed = perf_counter() - started
    return result, metrics, elapsed


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
        collision_limit = _tissu_collision_triangle_limit()
        if collision_surface is not None and collision_mode == "mesh" and collision_limit:
            collision_surface, collision_metrics, collision_seconds = _native_decimate_collision_surface(
                collision_surface,
                collision_limit,
            )
            print(
                "cloth-tissu-collision native_decimation source_triangles=%d solver_triangles=%d "
                "vertices=%d components=%d boundary_edges=%d nonmanifold_edges=%d wall_ms=%.3f"
                % (
                    len(self._source_collision_surface.triangles),
                    len(collision_surface.triangles),
                    collision_metrics["vertices"],
                    collision_metrics["components"],
                    collision_metrics["boundary_edges"],
                    collision_metrics["nonmanifold_edges"],
                    collision_seconds * 1000.0,
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
