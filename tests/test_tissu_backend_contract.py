from __future__ import annotations

import os
import sys
import types

import pytest

from freecad_cloth.simulation.ClothSolver import ClothSystem, Particle
from freecad_cloth.simulation import TissuBackend as module


class _FakeSolver:
    def __init__(self):
        self.stitches = []
        self.pins = []
        self.iterations = 0

    def add_stitch(self, a, b, compliance):
        self.stitches.append((int(a), int(b), float(compliance)))

    def add_pin(self, index, position, compliance):
        self.pins.append((int(index), tuple(position), float(compliance)))

    def set_iterations(self, value):
        self.iterations = int(value)


class _FakeFabric:
    class _Instance:
        @staticmethod
        def get_particle_indices():
            return [0, 1, 2]

    instance = _Instance()


class _FakeSimulation:
    def __init__(self, substeps, iterations, gravity, thickness):
        self.substeps = int(substeps)
        self.solver = _FakeSolver()
        self.gravity = float(gravity)
        self.positions = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]

    def create_from_arrays(self, name, vertices, triangles, material):
        self.positions = [tuple(float(v) for v in row) for row in vertices]
        return _FakeFabric()

    def step(self, dt):
        return None


def _backend(monkeypatch, delay=None):
    fake = types.SimpleNamespace(Simulation=_FakeSimulation)
    monkeypatch.setitem(sys.modules, "tissu", fake)
    if delay is None:
        monkeypatch.delenv("CLOTH_TISSU_STITCH_DELAY_STEPS", raising=False)
    else:
        monkeypatch.setenv("CLOTH_TISSU_STITCH_DELAY_STEPS", str(delay))
    system = ClothSystem([Particle(0.0,0.0,0.0), Particle(1.0,0.0,0.0), Particle(0.0,1.0,0.0)])
    return module.TissuBackend(system, ((0,1,2),), stitches=((0,1),))


def test_stitch_delay_defaults_off(monkeypatch):
    backend = _backend(monkeypatch)
    assert backend._stitches_active is True
    assert backend._stitch_delay_steps == 0
    assert backend._sim.solver.stitches == [(0,1,0.0)]


def test_stitch_delay_activates_before_expected_step(monkeypatch):
    backend = _backend(monkeypatch, delay=2)
    assert backend._sim.solver.stitches == []
    backend.step()
    assert backend._sim.solver.stitches == []
    backend.step()
    assert backend._sim.solver.stitches == []
    backend.step()
    assert backend._sim.solver.stitches == [(0,1,0.0)]
    assert backend._stitches_active is True
    assert backend._completed_steps == 3


def test_stitch_delay_resets_cleanly(monkeypatch):
    backend = _backend(monkeypatch, delay=2)
    backend.step()
    backend.step()
    assert backend._sim.solver.stitches == []
    backend.reset()
    assert backend._sim.solver.stitches == []
    assert backend._completed_steps == 0
    backend.step()
    assert backend._sim.solver.stitches == []
    backend.step()
    assert backend._sim.solver.stitches == []
    backend.step()
    assert backend._sim.solver.stitches == [(0,1,0.0)]


@pytest.mark.parametrize("value", ["-1", "-7"])
def test_stitch_delay_rejects_negative(monkeypatch, value):
    monkeypatch.setenv("CLOTH_TISSU_STITCH_DELAY_STEPS", value)
    with pytest.raises(ValueError, match="must be >= 0"):
        module._tissu_stitch_delay_steps()


def test_tunic_audit_enables_exact_fifteen_step_delay():
    source = open("tests/freecad_tunic_audit.py", encoding="utf-8").read()
    assert 'CLOTH_TISSU_STITCH_DELAY_STEPS"] = "15"' in source
    assert "activation-before-step=16" in source
