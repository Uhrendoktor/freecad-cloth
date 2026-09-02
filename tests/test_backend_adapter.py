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
