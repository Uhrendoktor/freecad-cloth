import sys
import types

import pytest

from freecad_cloth.simulation.ClothSolver import ClothSystem
from freecad_cloth.simulation.TissuBackend import TissuBackend


class FakeSolver:
    def __init__(self):
        self.added_stitches = []
        self.pins = []
        self.iterations = None

    def add_stitch(self, a, b, compliance):
        self.added_stitches.append((int(a), int(b), float(compliance)))

    def add_pin(self, index, position, compliance):
        self.pins.append((int(index), tuple(position), float(compliance)))

    def set_iterations(self, iterations):
        self.iterations = int(iterations)


class FakeFabricInstance:
    def __init__(self, count):
        self._ids = list(range(count))

    def get_particle_indices(self):
        return self._ids


class FakeFabric:
    def __init__(self, count):
        self.instance = FakeFabricInstance(count)


class FakeSimulation:
    last_instance = None

    def __init__(self, substeps, iterations, gravity, thickness):
        self.substeps = int(substeps)
        self.iterations = int(iterations)
        self.gravity = float(gravity)
        self.thickness = float(thickness)
        self.solver = FakeSolver()
        self.positions = []
        self.step_stitch_counts = []
        FakeSimulation.last_instance = self

    def create_from_arrays(self, name, vertices, triangles, material):
        self.positions = [tuple(float(value) for value in row) for row in vertices]
        return FakeFabric(len(self.positions))

    def add_mesh_from_arrays(self, name, vertices, triangles, friction):
        return None

    def step(self, dt):
        self.step_stitch_counts.append(len(self.solver.added_stitches))


def install_fake_tissu(monkeypatch):
    module = types.ModuleType("tissu")
    module.Simulation = FakeSimulation
    monkeypatch.setitem(sys.modules, "tissu", module)


def make_backend(monkeypatch, delay, stitches=((0, 1),)):
    install_fake_tissu(monkeypatch)
    monkeypatch.setenv("CLOTH_TISSU_STITCH_DELAY_STEPS", str(delay))
    system = ClothSystem.grid(20.0, 20.0, nx=2, ny=2)
    return TissuBackend(
        system,
        triangles=((0, 1, 3), (0, 3, 2)),
        stitches=stitches,
        collision_surface=None,
    )


def test_delay_zero_preserves_immediate_stitch_activation(monkeypatch):
    backend = make_backend(monkeypatch, 0)
    assert backend._stitches_armed is True
    assert FakeSimulation.last_instance.solver.added_stitches == [(0, 1, 0.0)]


def test_delayed_activation_occurs_only_before_step_after_boundary(monkeypatch):
    backend = make_backend(monkeypatch, 2)
    simulation = FakeSimulation.last_instance
    assert simulation.solver.added_stitches == []

    backend.step(iterations=1)
    backend.step(iterations=1)
    assert simulation.step_stitch_counts == [0, 0]
    assert backend._stitch_steps == 2

    backend.step(iterations=1)
    assert simulation.step_stitch_counts == [0, 0, 1]
    assert simulation.solver.added_stitches == [(0, 1, 0.0)]
    assert backend._stitches_armed is True
    assert backend._stitch_steps == 3


def test_set_stitches_updates_deferred_pair_set_before_activation(monkeypatch):
    backend = make_backend(monkeypatch, 2, stitches=((0, 1),))
    simulation = FakeSimulation.last_instance
    backend.set_stitches(((1, 2),))
    assert simulation.solver.added_stitches == []

    backend.step(iterations=1)
    backend.step(iterations=1)
    backend.step(iterations=1)

    assert simulation.solver.added_stitches == [(1, 2, 0.0)]


def test_delayed_activation_preserves_requested_compliance(monkeypatch):
    backend = make_backend(monkeypatch, 2, stitches=((0, 1),))
    simulation = FakeSimulation.last_instance
    backend.set_stitches(((1, 2),), compliance=0.125)
    backend.step(iterations=1)
    backend.step(iterations=1)
    backend.step(iterations=1)
    assert simulation.solver.added_stitches == [(1, 2, 0.125)]


def test_reset_restarts_delay_window(monkeypatch):
    backend = make_backend(monkeypatch, 2)
    backend.step(iterations=1)
    backend.step(iterations=1)
    backend.step(iterations=1)
    assert backend._stitch_steps == 3

    backend.reset()
    simulation = FakeSimulation.last_instance
    assert backend._stitch_steps == 0
    assert backend._stitches_armed is False
    assert simulation.solver.added_stitches == []

    backend.step(iterations=1)
    backend.step(iterations=1)
    assert simulation.step_stitch_counts == [0, 0]
    backend.step(iterations=1)
    assert simulation.step_stitch_counts == [0, 0, 1]


def test_delay_parser_rejects_negative_values(monkeypatch):
    monkeypatch.delenv("CLOTH_TISSU_STITCH_DELAY_STEPS", raising=False)
    from freecad_cloth.simulation.TissuBackend import _tissu_stitch_delay_steps

    assert _tissu_stitch_delay_steps() == 0
    monkeypatch.setenv("CLOTH_TISSU_STITCH_DELAY_STEPS", "15")
    assert _tissu_stitch_delay_steps() == 15
    monkeypatch.setenv("CLOTH_TISSU_STITCH_DELAY_STEPS", "-1")
    with pytest.raises(ValueError, match="must be >= 0"):
        _tissu_stitch_delay_steps()
