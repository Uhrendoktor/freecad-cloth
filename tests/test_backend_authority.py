import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freecad_cloth.simulation.ClothBackend import (
    ClothSimulationBackend,
    XPBDBackend,
    default_backend_registry,
)
from freecad_cloth.simulation.SimulationBackend import NullSolver
from freecad_cloth.simulation.ClothSolver import ClothSystem


def test_default_registry_exposes_single_reference_backend():
    registry = default_backend_registry()
    backend = registry.create("xpbd-cpu", ClothSystem.grid(20.0, 10.0, 3, 2))
    assert isinstance(backend, ClothSimulationBackend)
    assert isinstance(backend, XPBDBackend)
    assert backend.name == "xpbd-cpu"


def test_backend_drives_solver_and_reset_restores_initial_state():
    backend = default_backend_registry().create("xpbd-cpu", ClothSystem.grid(20.0, 10.0, 3, 2))
    initial = backend.positions()
    backend.pin((0, 2))
    backend.step(dt=1.0 / 60.0, iterations=2, gravity=(0.0, 0.0, -9810.0))
    assert backend.time > 0.0
    assert backend.finite()
    backend.reset()
    assert backend.time == 0.0
    assert backend.positions() == initial


def test_backend_boundary_does_not_expose_solver_step_requirement():
    names = {name for name in ("step", "reset", "pin", "set_stitches", "positions", "finite") if hasattr(ClothSimulationBackend, name)}
    assert names == {"step", "reset", "pin", "set_stitches", "positions", "finite"}


if __name__ == "__main__":
    for name, fn in globals().copy().items():
        if name.startswith("test_"):
            fn()
    print("backend authority tests passed")
