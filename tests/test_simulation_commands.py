"""Behavioral tests for Simulation workbench command lifecycle helpers."""

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


def test_run_simulation_delegates_to_selected_simulation_without_implicit_creation():
    calls = []

    def simulate(steps: int | None = None) -> str:
        calls.append(steps)
        return "scene"

    assert SimulationCommands.run_simulation(simulate=simulate) == "scene"
    assert SimulationCommands.run_simulation(7, simulate=simulate) == "scene"
    assert calls == [30, 7]


def test_require_drape_target_ready_returns_target_and_rejects_blocked_state():
    target = object()
    doc = SimpleNamespace(Objects=[target])

    def find_target(_doc: object) -> object:
        return target

    def ready(_target: object) -> dict[str, str]:
        return {"state": "ready", "message": "ok"}

    assert (
        SimulationCommands._require_drape_target_ready(
            doc, find_target=find_target, target_status_fn=ready
        )
        is target
    )

    def blocked(_target: object) -> dict[str, str]:
        return {"state": "stale", "message": "Drape target changed"}

    try:
        SimulationCommands._require_drape_target_ready(
            doc, find_target=find_target, target_status_fn=blocked
        )
    except RuntimeError as exc:
        assert str(exc) == "Drape target changed"
    else:
        raise AssertionError("blocked drape targets must stop simulation")


def test_reset_simulation_resets_scene_and_recomputes():
    calls = []
    document = SimpleNamespace(recompute=lambda: calls.append("recompute"))
    scene = SimpleNamespace(Document=document)

    def require_simulation() -> tuple[object, object]:
        return document, scene

    def reset_scene(value: object) -> None:
        calls.append(("reset", value))

    assert (
        SimulationCommands.reset_simulation(
            require_simulation_fn=require_simulation,
            reset_scene_fn=reset_scene,
            refresh_overlay_fn=lambda _document: None,
        )
        is scene
    )
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
