import sys
import types

import pytest

from freecad_cloth.simulation.ClothSolver import ClothSystem, Particle
from freecad_cloth.simulation.TissuBackend import TissuBackend, _tissu_stitch_delay_steps


class _FakeSolver:
    def __init__(self):
        self.stitches = []
        self.pins = []
        self.iterations = None

    def add_stitch(self, a, b, rest_length):
        self.stitches.append((int(a), int(b), float(rest_length)))

    def add_pin(self, index, position, compliance):
        self.pins.append((int(index), tuple(float(v) for v in position), float(compliance)))

    def set_iterations(self, value):
        self.iterations = int(value)


class _FakeFabricInstance:
    def __init__(self, count):
        self._count = count

    def get_particle_indices(self):
        return list(range(self._count))


class _FakeFabric:
    def __init__(self, count):
        self.instance = _FakeFabricInstance(count)


class _FakeSimulation:
    def __init__(self, substeps, iterations, gravity, thickness):
        self.substeps = int(substeps)
        self.iterations = int(iterations)
        self.gravity = float(gravity)
        self.thickness = float(thickness)
        self.solver = _FakeSolver()
        self.positions = []

    def create_from_arrays(self, name, vertices, triangles, material):
        self.positions = [tuple(float(v) for v in vertex) for vertex in vertices]
        return _FakeFabric(len(self.positions))

    def add_mesh_from_arrays(self, name, vertices, triangles, friction):
        return None

    def add_sphere(self, name, center, radius, friction):
        return None

    def step(self, dt):
        return None


@pytest.fixture
def fake_tissu(monkeypatch):
    monkeypatch.setitem(sys.modules, "tissu", types.SimpleNamespace(Simulation=_FakeSimulation))


def _make_backend(monkeypatch, delay):
    if delay is None:
        monkeypatch.delenv("CLOTH_TISSU_STITCH_DELAY_STEPS", raising=False)
    else:
        monkeypatch.setenv("CLOTH_TISSU_STITCH_DELAY_STEPS", str(delay))
    system = ClothSystem([Particle(0.0, 0.0, 0.0), Particle(25.0, 0.0, 0.0)])
    return TissuBackend(system, triangles=(), stitches=((0, 1),))


def test_stitch_delay_parser_is_bounded(monkeypatch):
    monkeypatch.setenv("CLOTH_TISSU_STITCH_DELAY_STEPS", "15")
    assert _tissu_stitch_delay_steps() == 15
    monkeypatch.setenv("CLOTH_TISSU_STITCH_DELAY_STEPS", "-1")
    with pytest.raises(ValueError):
        _tissu_stitch_delay_steps()


def test_default_stitches_are_immediate(fake_tissu, monkeypatch):
    backend = _make_backend(monkeypatch, None)
    assert backend.stitch_delay_steps == 0
    assert backend.stitch_activation_step == 0
    assert backend._sim.solver.stitches == [(0, 1, 0.0)]


def test_delayed_stitches_activate_before_step_16(fake_tissu, monkeypatch):
    backend = _make_backend(monkeypatch, 15)
    assert backend.stitch_activation_step is None
    assert backend._sim.solver.stitches == []

    for expected_step in range(1, 16):
        backend.step(dt=1.0 / 60.0, iterations=1, gravity=(0.0, 0.0, 0.0))
        assert backend._stitch_step == expected_step
        assert backend._sim.solver.stitches == []
        assert backend.stitch_activation_step is None

    backend.step(dt=1.0 / 60.0, iterations=1, gravity=(0.0, 0.0, 0.0))
    assert backend._stitch_step == 16
    assert backend.stitch_activation_step == 16
    assert backend._sim.solver.stitches == [(0, 1, 0.0)]


def test_delayed_stitches_reset_to_pending(fake_tissu, monkeypatch):
    backend = _make_backend(monkeypatch, 15)
    for _ in range(16):
        backend.step(dt=1.0 / 60.0, iterations=1, gravity=(0.0, 0.0, 0.0))
    assert backend.stitch_activation_step == 16
    backend.reset()
    assert backend.stitch_activation_step is None
    assert backend._sim.solver.stitches == []
    for _ in range(16):
        backend.step(dt=1.0 / 60.0, iterations=1, gravity=(0.0, 0.0, 0.0))
    assert backend.stitch_activation_step == 16
    assert backend._sim.solver.stitches == [(0, 1, 0.0)]
