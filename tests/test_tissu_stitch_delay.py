import sys
import types

import pytest

from freecad_cloth.simulation.ClothSolver import ClothSystem
from freecad_cloth.simulation.TissuBackend import TissuBackend, _tissu_stitch_delay_steps


class _FakeSolver:
    def __init__(self):
        self.stitches = []
        self.pins = []
        self.iterations = 8

    def add_stitch(self, a, b, compliance):
        self.stitches.append((int(a), int(b), float(compliance)))

    def add_pin(self, index, position, compliance):
        self.pins.append((int(index), tuple(position), float(compliance)))

    def set_iterations(self, iterations):
        self.iterations = int(iterations)


class _FakeInstance:
    def __init__(self, count):
        self._count = int(count)

    def get_particle_indices(self):
        return list(range(self._count))


class _FakeFabric:
    def __init__(self, count):
        self.instance = _FakeInstance(count)


class _FakeSimulation:
    last = None

    def __init__(self, substeps=1, iterations=8, gravity=-9.81, thickness=0.002):
        self.substeps = int(substeps)
        self.gravity = float(gravity)
        self.solver = _FakeSolver()
        self.positions = []
        self.time = 0.0
        _FakeSimulation.last = self

    def create_from_arrays(self, _name, vertices, _triangles, material="cotton"):
        self.positions = [tuple(v) for v in vertices]
        return _FakeFabric(len(self.positions))

    def add_mesh_from_arrays(self, *_args, **_kwargs):
        return None

    def step(self, dt):
        self.time += float(dt)


@pytest.fixture
def fake_tissu(monkeypatch):
    module = types.SimpleNamespace(Simulation=_FakeSimulation)
    monkeypatch.setitem(sys.modules, "tissu", module)
    return module


def _make_backend(monkeypatch, delay, fake_tissu):
    if delay is None:
        monkeypatch.delenv("CLOTH_TISSU_STITCH_DELAY_STEPS", raising=False)
    else:
        monkeypatch.setenv("CLOTH_TISSU_STITCH_DELAY_STEPS", str(delay))
    system = ClothSystem.grid(20.0, 20.0, nx=3, ny=3)
    return TissuBackend(
        system,
        triangles=((0, 1, 4), (0, 4, 3)),
        stitches=((0, 1),),
    )


def test_tissu_stitch_delay_parsing_is_default_off_and_fail_closed(monkeypatch):
    monkeypatch.delenv("CLOTH_TISSU_STITCH_DELAY_STEPS", raising=False)
    assert _tissu_stitch_delay_steps() == 0
    monkeypatch.setenv("CLOTH_TISSU_STITCH_DELAY_STEPS", "15")
    assert _tissu_stitch_delay_steps() == 15
    monkeypatch.setenv("CLOTH_TISSU_STITCH_DELAY_STEPS", "-1")
    with pytest.raises(ValueError, match="must be >= 0"):
        _tissu_stitch_delay_steps()


def test_tissu_delayed_stitches_activate_before_step_after_delay(monkeypatch, fake_tissu):
    backend = _make_backend(monkeypatch, 2, fake_tissu)
    solver = _FakeSimulation.last.solver
    assert solver.stitches == []

    backend.step(dt=1.0 / 60.0, iterations=1)
    assert solver.stitches == []

    backend.step(dt=1.0 / 60.0, iterations=1)
    assert solver.stitches == []

    backend.step(dt=1.0 / 60.0, iterations=1)
    assert solver.stitches == [(0, 1, 0.0)]
    assert backend._backend_steps == 3
    assert backend._stitches_activated


def test_tissu_delayed_stitch_activation_does_not_duplicate(monkeypatch, fake_tissu):
    backend = _make_backend(monkeypatch, 1, fake_tissu)
    solver = _FakeSimulation.last.solver
    backend.step(dt=1.0 / 60.0, iterations=1)
    assert solver.stitches == []
    backend.step(dt=1.0 / 60.0, iterations=1)
    backend.step(dt=1.0 / 60.0, iterations=1)
    assert solver.stitches == [(0, 1, 0.0)]


def test_tissu_delayed_stitch_reset_restores_unactivated_state(monkeypatch, fake_tissu):
    backend = _make_backend(monkeypatch, 1, fake_tissu)
    backend.step(dt=1.0 / 60.0, iterations=1)
    backend.step(dt=1.0 / 60.0, iterations=1)
    assert backend._stitches_activated
    backend.reset()
    assert not backend._stitches_activated
    assert backend._backend_steps == 0
    assert _FakeSimulation.last.solver.stitches == []
