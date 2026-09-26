from types import ModuleType, SimpleNamespace
import sys

from freecad_cloth.simulation.ClothSolver import ClothSystem
from freecad_cloth.simulation.TissuBackend import TissuBackend


class _FakeSolver:
    def __init__(self):
        self.iteration_calls = []
        self.pin_calls = []
        self.stitch_calls = []

    def set_iterations(self, value):
        self.iteration_calls.append(int(value))

    def add_pin(self, index, position, compliance):
        self.pin_calls.append((index, tuple(position), compliance))

    def add_stitch(self, a, b, compliance):
        self.stitch_calls.append((a, b, compliance))


class _FakeFabricInstance:
    def __init__(self, count):
        self._count = count

    def get_particle_indices(self):
        return list(range(self._count))


class _FakeFabric:
    def __init__(self, count):
        self.instance = _FakeFabricInstance(count)


class _FakeSimulation:
    created = []

    def __init__(self, *, substeps, iterations, gravity, thickness):
        self.substeps = substeps
        self.iterations = iterations
        self.gravity = gravity
        self.thickness = thickness
        self.solver = _FakeSolver()
        self.step_calls = []
        self._positions = ()
        type(self).created.append(self)

    def create_from_arrays(self, name, vertices, triangles, material):
        self._positions = tuple(tuple(float(c) for c in vertex) for vertex in vertices)
        return _FakeFabric(len(vertices))

    def step(self, dt):
        self.step_calls.append(float(dt))

    @property
    def positions(self):
        return self._positions


def test_tissu_backend_caches_invariant_solver_state(monkeypatch):
    # Reapplying invariant solver controls per physics step can rebuild native state.
    fake_tissu = ModuleType("tissu")
    fake_tissu.Simulation = _FakeSimulation
    _FakeSimulation.created.clear()
    monkeypatch.setitem(sys.modules, "tissu", fake_tissu)

    system = ClothSystem.grid(20.0, 20.0, nx=2, ny=2)
    backend = TissuBackend(
        system,
        triangles=((0, 1, 3), (0, 3, 2)),
        pins=(0,),
        collision_surface=None,
    )

    backend.step(iterations=4, gravity=(0.0, 0.0, -9810.0))
    backend.step(iterations=4, gravity=(0.0, 0.0, -9810.0))
    backend.step(iterations=6, gravity=(0.0, 0.0, -9810.0))

    sim = _FakeSimulation.created[-1]
    assert sim.solver.iteration_calls == [4, 6]
    assert sim.step_calls == [1.0 / 60.0] * 3
    assert sim.gravity == -9.81

    backend.reset()
    backend.step(iterations=4, gravity=(0.0, 0.0, -9810.0))
    reset_sim = _FakeSimulation.created[-1]
    assert reset_sim.solver.iteration_calls == [4]
