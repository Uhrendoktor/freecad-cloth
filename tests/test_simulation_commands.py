# Copyright (C) 2026 FreeCAD Cloth contributors
"""Behavioral tests for Simulation workbench command lifecycle helpers."""

from types import SimpleNamespace

from freecad_cloth.simulation import SimulationCommands
from tests.support.assertions import require


def test_public_simulation_command_surface_is_unique() -> None:
    """Keep the public simulation command identifiers unique and stable."""
    require(
        condition=SimulationCommands.COMMANDS
        == [
            "ClothSimulation_Create",
            "ClothSimulation_CreateDrape",
            "ClothSimulation_Edit",
            "ClothSimulation_Step",
            "ClothSimulation_Run",
            "ClothSimulation_Reset",
        ],
        message="The simulation workbench must expose its six stable command identifiers.",
    )


def test_run_simulation_delegates_to_selected_simulation_without_implicit_creation() -> None:
    """Delegate the requested step count without creating a simulation implicitly."""
    calls: list[int | None] = []

    def simulate(steps: int | None = None) -> str:
        """Record the delegated step count and return the simulated scene label.

        Args:
            steps: Optional number of simulation steps passed by the caller.

        Returns:
            The scene label returned by the selected simulation.
        """
        calls.append(steps)
        return "scene"

    require(
        condition=SimulationCommands.run_simulation(simulate=simulate) == "scene",
        message="The default simulation run must return the selected scene result.",
    )
    require(
        condition=SimulationCommands.run_simulation(7, simulate=simulate) == "scene",
        message="An explicit step count must return the selected scene result.",
    )
    require(
        condition=calls == [30, 7],
        message="The command must delegate the default and explicit step counts in order.",
    )


def test_require_drape_target_ready_returns_target_and_rejects_blocked_state() -> None:
    """Return the ready drape target and reject a stale target with its status message.

    Raises:
        AssertionError: If a blocked drape target is accepted or its message changes.
    """
    target = object()
    doc = SimpleNamespace(Objects=[target])

    def find_target(_doc: object) -> object:
        """Return the test target selected from the supplied document.

        Args:
            _doc: Document whose target lookup is being exercised.

        Returns:
            The target object used by this regression test.
        """
        return target

    def ready(_target: object) -> dict[str, str]:
        """Describe a target that is ready for simulation.

        Args:
            _target: Target whose status is requested.

        Returns:
            A ready status with a non-error message.
        """
        return {"state": "ready", "message": "ok"}

    require(
        condition=(
            SimulationCommands._require_drape_target_ready(
                doc, find_target=find_target, target_status_fn=ready
            )
            is target
        ),
        message="A ready drape target must be returned unchanged.",
    )

    def blocked(_target: object) -> dict[str, str]:
        """Describe a target that must not be used by the simulation.

        Args:
            _target: Target whose status is requested.

        Returns:
            A stale status containing the user-facing rejection message.
        """
        return {"state": "stale", "message": "Drape target changed"}

    try:
        SimulationCommands._require_drape_target_ready(
            doc, find_target=find_target, target_status_fn=blocked
        )
    except RuntimeError as exc:
        require(
            condition=str(exc) == "Drape target changed",
            message="A blocked target must preserve its status message.",
        )
    else:
        msg = "blocked drape targets must stop simulation"
        raise AssertionError(msg)


def test_reset_simulation_resets_scene_and_recomputes() -> None:
    """Reset the scene and recompute its document exactly once."""
    calls: list[object] = []
    document = SimpleNamespace(recompute=lambda: calls.append("recompute"))
    scene = SimpleNamespace(Document=document)

    def require_simulation() -> tuple[object, object]:
        """Return the active document and its selected simulation scene.

        Returns:
            The document and scene fixture supplied to the reset command.
        """
        return document, scene

    def reset_scene(value: object) -> None:
        """Record the scene passed to the reset operation.

        Args:
            value: Simulation scene whose state must be reset.
        """
        calls.append(("reset", value))

    require(
        condition=(
            SimulationCommands.reset_simulation(
                require_simulation_fn=require_simulation,
                reset_scene_fn=reset_scene,
                refresh_overlay_fn=lambda _document: None,
            )
            is scene
        ),
        message="Reset must return the selected simulation scene.",
    )
    require(
        condition=calls == [("reset", scene), "recompute"],
        message="Reset must reset the scene before recomputing its document.",
    )


def test_simulation_command_resources_and_activation_are_runtime_objects() -> None:
    """Expose runtime command activation and the expected FreeCAD resource values."""
    command = SimulationCommands._FunctionCommand(
        lambda: 17,
        "Run",
        "run simulation",
        "ClothSimulation_Run",
        active=lambda: True,
    )
    require(condition=command.IsActive(), message="An active command must be enabled.")
    require(
        condition=command.Activated() == 17,
        message="Activation must return the command callback result.",
    )
    resources = command.GetResources()
    require(
        condition=resources["MenuText"] == "Run",
        message="The command menu text must match its configured label.",
    )
    require(
        condition=resources["ToolTip"] == "run simulation",
        message="The command tooltip must match its configured description.",
    )
    require(
        condition=bool(resources["Pixmap"]),
        message="The command resources must include its icon path.",
    )


def test_simulation_command_resource_activity_is_false_when_predicate_is_false() -> None:
    """Disable a command when its optional activity predicate returns false."""
    command = SimulationCommands._FunctionCommand(
        lambda: None,
        "Run",
        "run simulation",
        "ClothSimulation_Run",
        active=lambda: False,
    )
    require(
        condition=not command.IsActive(),
        message="A command with a false activity predicate must be disabled.",
    )
