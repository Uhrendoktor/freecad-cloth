import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from freecad_cloth.simulation.ClothSolver import ClothSystem
from freecad_cloth.simulation.ClothBackend import (
    ClothSimulationBackend,
    XPBDBackend,
    default_backend_registry,
)
from freecad_cloth.simulation.SimulationBackend import ClothState, NullSolver
from freecad_cloth.pattern.PatternModel import PatternPiece, Seam
from freecad_cloth.sewing.SeamGraph import SeamGraph


def test_registry_selects_xpbd_backend_without_changing_solver_api():
    system = ClothSystem.grid(20, 20, nx=3, ny=3)
    backend = default_backend_registry().create("xpbd-cpu", system)
    assert isinstance(backend, XPBDBackend)
    before = backend.positions()
    backend.step(dt=1.0 / 60.0, iterations=4)
    assert backend.time == pytest.approx(1.0 / 60.0)
    assert backend.positions() != before
    assert backend.finite()


def test_reset_replays_pins_and_stitches_deterministically():
    system = ClothSystem.grid(20, 20, nx=3, ny=3)
    backend = XPBDBackend(system)
    initial = backend.positions()
    backend.pin([0])
    backend.set_stitches([(1, 2)])
    backend.step(iterations=4)
    advanced = backend.positions()
    assert advanced != initial
    backend.reset()
    reset = backend.positions()
    assert reset == initial
    assert backend.system.pins == {0: initial[0]}
    assert len(backend.system.stitches) == 1


def test_semantic_seams_feed_backend_but_graph_remains_unchanged():
    graph = SeamGraph()
    graph.add_piece(PatternPiece("a", [(0, 0), (10, 0), (10, 10)], id="a"))
    graph.add_piece(PatternPiece("b", [(0, 0), (10, 0), (10, 10)], id="b"))
    graph.add_seam(Seam("a", 0, "b", 0, id="join"))
    metadata = graph.to_metadata()
    backend = XPBDBackend(ClothSystem.grid(10, 10, nx=3, ny=3))
    backend.set_seams(graph, {
        ("a", 0): (0, 1, 2),
        ("b", 0): (3, 4, 5),
    })
    assert len(backend.system.stitches) == 3
    assert graph.to_metadata() == metadata


def test_registry_rejects_duplicate_or_invalid_backend_factories():
    registry = default_backend_registry()
    with pytest.raises(ValueError, match="already registered"):
        registry.register("xpbd-cpu", XPBDBackend)
    registry.register("fake", lambda system: object())
    with pytest.raises(TypeError, match="ClothSimulationBackend"):
        registry.create("fake", ClothSystem.grid(5, 5, nx=2, ny=2))
    with pytest.raises(ValueError, match="unknown cloth backend"):
        registry.create("missing", ClothSystem.grid(5, 5, nx=2, ny=2))


def test_adapter_interface_is_abstract():
    with pytest.raises(TypeError):
        ClothSimulationBackend()



def _install_fake_tissu(monkeypatch):
    import types

    import numpy as np

    class FakeSolver:
        def __init__(self):
            self.stitches = []
            self.pins = []
            self.iterations = None

        def add_stitch(self, a, b, compliance):
            self.stitches.append((int(a), int(b), float(compliance)))

        def add_pin(self, index, position, compliance):
            self.pins.append((int(index), tuple(float(v) for v in position), float(compliance)))

        def set_iterations(self, value):
            self.iterations = int(value)

    class FakeFabricInstance:
        def __init__(self, count):
            self._indices = np.arange(count, dtype=np.int32)

        def get_particle_indices(self):
            return self._indices

    class FakeFabric:
        def __init__(self, count):
            self.instance = FakeFabricInstance(count)

    class FakeSimulation:
        instances = []

        def __init__(self, substeps=10, iterations=2, gravity=-9.81, thickness=0.02):
            self.solver = FakeSolver()
            self.positions = np.empty((0, 3), dtype=np.float64)
            self.gravity = float(gravity)
            self.substeps = int(substeps)
            self.iterations = int(iterations)
            self.step_calls = []
            self.colliders = []
            type(self).instances.append(self)

        def create_from_arrays(self, name, vertices, triangles, material="cotton"):
            self.positions = np.asarray(vertices, dtype=np.float64)
            return FakeFabric(len(self.positions))

        def add_mesh_from_arrays(self, name, vertices, triangles, friction=0.5):
            self.colliders.append((name, "mesh", float(friction)))

        def add_sphere(self, name, center, radius, friction=0.5):
            self.colliders.append((name, "sphere", float(radius), float(friction)))

        def step(self, dt):
            self.step_calls.append(float(dt))

    module = types.ModuleType("tissu")
    module.Simulation = FakeSimulation
    monkeypatch.setitem(sys.modules, "tissu", module)
    return FakeSimulation



def test_tissu_set_stitches_replaces_before_step_and_preserves_compliance(monkeypatch):
    FakeSimulation = _install_fake_tissu(monkeypatch)

    from freecad_cloth.simulation.TissuBackend import TissuBackend

    system = ClothSystem.grid(20, 20, nx=3, ny=2)
    triangles = ((0, 1, 4), (0, 4, 3), (1, 2, 5), (1, 5, 4))
    backend = TissuBackend(system, triangles=triangles, stitches=((1, 2),))

    assert backend._sim.solver.stitches == [(1, 2, 0.0)]

    backend.set_stitches(((2, 3),), compliance=0.25)

    assert backend._stitches == ((2, 3),)
    assert backend._stitch_compliance == pytest.approx(0.25)
    assert backend._sim.solver.stitches == [(2, 3, 0.25)]

    backend.step(iterations=4)
    backend.reset()

    assert backend._sim.solver.stitches == [(2, 3, 0.25)]
    assert FakeSimulation.instances[-1] is backend._sim


def test_tissu_set_stitches_fails_closed_after_step(monkeypatch):
    _install_fake_tissu(monkeypatch)

    from freecad_cloth.simulation.TissuBackend import TissuBackend

    system = ClothSystem.grid(20, 20, nx=3, ny=2)
    triangles = ((0, 1, 4), (0, 4, 3), (1, 2, 5), (1, 5, 4))
    backend = TissuBackend(system, triangles=triangles, stitches=((1, 2),))

    backend.step()

    with pytest.raises(RuntimeError, match="cannot replace stitches after simulation has advanced"):
        backend.set_stitches(((2, 3),))

    assert backend._sim.solver.stitches == [(1, 2, 0.0)]
