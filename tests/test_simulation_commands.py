"""Behavioral tests for Simulation workbench command lifecycle helpers."""

import sys
from types import SimpleNamespace

from freecad_cloth.simulation import SimulationCommands


def test_public_simulation_command_surface_is_unique():
    assert SimulationCommands.COMMANDS == [
        "ClothSimulation_Create",
        "ClothSimulation_CreateDrape",
        "ClothSimulation_Edit",
        "ClothSimulation_Step",
        "ClothSimulation_Run",
        "ClothSimulation_Reset",
    ]


def test_run_simulation_delegates_to_selected_simulation_without_implicit_creation(monkeypatch):
    calls = []
    monkeypatch.setattr(
        SimulationCommands,
        "simulate_selected",
        lambda steps=None: calls.append(steps) or "scene",
    )
    assert SimulationCommands.run_simulation() == "scene"
    assert SimulationCommands.run_simulation(7) == "scene"
    assert calls == [30, 7]


def test_require_drape_target_ready_returns_target_and_rejects_blocked_state(monkeypatch):
    target = object()
    doc = SimpleNamespace(Objects=[target])

    monkeypatch.setattr(
        SimulationCommands,
        "_find_drape_target",
        lambda _doc: target,
    )
    monkeypatch.setitem(
        sys.modules,
        "freecad_cloth.simulation.DrapeTarget",
        SimpleNamespace(target_status=lambda _target: {"state": "ready", "message": "ok"}),
    )
    assert SimulationCommands._require_drape_target_ready(doc) is target

    monkeypatch.setitem(
        sys.modules,
        "freecad_cloth.simulation.DrapeTarget",
        SimpleNamespace(
            target_status=lambda _target: {
                "state": "stale",
                "message": "Drape target changed",
            }
        ),
    )
    try:
        SimulationCommands._require_drape_target_ready(doc)
    except RuntimeError as exc:
        assert str(exc) == "Drape target changed"
    else:
        raise AssertionError("blocked drape targets must stop simulation")


def test_reset_simulation_resets_scene_and_recomputes(monkeypatch):
    calls = []
    document = SimpleNamespace(recompute=lambda: calls.append("recompute"))
    scene = SimpleNamespace(Document=document)
    monkeypatch.setattr(
        SimulationCommands,
        "_require_simulation",
        lambda: (document, scene),
    )
    monkeypatch.setitem(
        sys.modules,
        "freecad_cloth.simulation.SimulationObjects",
        SimpleNamespace(reset_scene=lambda value: calls.append(("reset", value))),
    )
    assert SimulationCommands.reset_simulation() is scene
    assert calls == [("reset", scene), "recompute"]


def test_simulation_command_resources_and_activation_are_runtime_objects():
    command = SimulationCommands._FunctionCommand(
        lambda: 17,
        "Run",
        "run simulation",
        "ClothSimulation_Run",
        active=lambda: True,
    )
    assert command.IsActive()
    assert command.Activated() == 17
    resources = command.GetResources()
    assert resources["MenuText"] == "Run"
    assert resources["ToolTip"] == "run simulation"
    assert resources["Pixmap"]


def test_simulation_command_resource_activity_is_false_when_predicate_is_false():
    command = SimulationCommands._FunctionCommand(
        lambda: None,
        "Run",
        "run simulation",
        "ClothSimulation_Run",
        active=lambda: False,
    )
    assert not command.IsActive()
