# Copyright (C) 2026 FreeCAD Cloth contributors
"""Behavioral tests for Simulation workbench command lifecycle helpers."""

import importlib
import sys
from types import ModuleType, SimpleNamespace
from typing import TYPE_CHECKING, TypedDict, cast

if TYPE_CHECKING:
    from collections.abc import Callable

import pytest

from freecad_cloth.sewing import SeamOverlay
from freecad_cloth.simulation import DrapeTarget, SimulationCommands
from freecad_cloth.simulation.simulation_protocols import SimulationDocument, SimulationScene
from tests.support.assertions import require

DEFAULT_SIMULATION_STEPS = 30
EXPLICIT_SIMULATION_STEPS = 7
_FREECAD_ACTIVATED_METHOD = "Activated"
_FREECAD_GET_RESOURCES_METHOD = "GetResources"
_FREECAD_IS_ACTIVE_METHOD = "IsActive"


class _TargetStatus(TypedDict):
    """Status fields returned by the target-readiness fixture."""

    state: str
    message: str
    stale: bool
    reason: str


def _ready_target_status(_target: object | None) -> _TargetStatus:
    """Describe a target whose collision surface is ready for simulation.

    Args:
        _target: Persistent drape target whose readiness is being checked.

    Returns:
        A non-stale ready status with an empty invalidation reason.
    """
    return {"state": "ready", "message": "ok", "stale": False, "reason": ""}


def _blocked_target_status(_target: object | None) -> _TargetStatus:
    """Describe a stale target that must block simulation advancement.

    Args:
        _target: Persistent drape target whose readiness is being checked.

    Returns:
        A stale status containing the user-facing rejection message.
    """
    return {
        "state": "stale",
        "message": "Drape target changed",
        "stale": True,
        "reason": "source changed",
    }


def _install_freecad_scene(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[ModuleType, SimpleNamespace, list[str]]:
    """Install a minimal FreeCAD document for public simulation-command tests.

    Args:
        monkeypatch: Fixture that restores the injected host modules and callbacks.

    Returns:
        The fake FreeCAD module, its simulation scene, and recorded document callbacks.
    """
    calls: list[str] = []
    scene = SimpleNamespace(Name="ClothSimulation", Steps=0)
    target = SimpleNamespace(Name="DrapeTarget", TargetType="Mannequin")
    document = SimpleNamespace(
        Objects=[scene, target],
        recompute=lambda: calls.append("recompute"),
    )
    scene.Document = document
    app_module = ModuleType("FreeCAD")
    app_module.__dict__["ActiveDocument"] = document
    monkeypatch.setitem(sys.modules, "FreeCAD", app_module)
    monkeypatch.setattr(DrapeTarget, "target_status", _ready_target_status)

    def record_overlay_refresh(_document: object) -> None:
        """Record a seam-overlay refresh requested by a public command.

        Args:
            _document: FreeCAD document passed to the overlay refresh callback.
        """
        calls.append("refresh")

    monkeypatch.setattr(
        SeamOverlay,
        "refresh_seam_overlay",
        record_overlay_refresh,
    )
    return app_module, scene, calls


def _register_workbench_commands(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[ModuleType, SimpleNamespace, list[str], dict[str, object]]:
    """Capture command objects registered through the public FreeCAD GUI boundary.

    Args:
        monkeypatch: Fixture that restores the fake GUI module after registration.

    Returns:
        The fake FreeCAD module, simulation scene, callback log, and registered commands.
    """
    app_module, scene, calls = _install_freecad_scene(monkeypatch)
    registered: dict[str, object] = {}
    gui_module = ModuleType("FreeCADGui")

    def add_command(command_name: str, command: object) -> None:
        """Record a command registered by the Simulation workbench.

        Args:
            command_name: Stable FreeCAD command identifier.
            command: Runtime command object associated with the identifier.
        """
        registered[command_name] = command

    gui_module.__dict__["addCommand"] = add_command
    monkeypatch.setitem(sys.modules, "FreeCADGui", gui_module)
    # Register against the injected GUI module without mutating the module's read-only vars view.
    monkeypatch.setattr(SimulationCommands, "Gui", None, raising=False)
    importlib.reload(SimulationCommands)
    return app_module, scene, calls, registered


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
        condition=SimulationCommands.run_simulation(EXPLICIT_SIMULATION_STEPS, simulate=simulate)
        == "scene",
        message="An explicit step count must return the selected scene result.",
    )
    require(
        condition=calls == [DEFAULT_SIMULATION_STEPS, EXPLICIT_SIMULATION_STEPS],
        message="The command must delegate the default and explicit step counts in order.",
    )


def test_simulate_selected_blocks_a_stale_target_before_advancing_the_scene(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Advance a ready scene and leave it unchanged when the target becomes stale.

    Args:
        monkeypatch: Fixture that installs a controlled FreeCAD scene and target state.
    """
    _app_module, scene, calls = _install_freecad_scene(monkeypatch)
    result = SimulationCommands.simulate_selected(EXPLICIT_SIMULATION_STEPS)
    require(
        condition=result is scene,
        message="Simulation stepping must return the selected scene when no drape panels exist.",
    )
    require(
        condition=scene.Steps == EXPLICIT_SIMULATION_STEPS,
        message="A ready target must allow the requested number of simulation steps.",
    )
    require(
        condition=calls == ["recompute", "refresh"],
        message="A successful step must recompute the document and refresh seam overlays.",
    )

    scene.Steps = 0
    calls.clear()
    monkeypatch.setattr(DrapeTarget, "target_status", _blocked_target_status)
    with pytest.raises(RuntimeError) as error:
        SimulationCommands.simulate_selected(EXPLICIT_SIMULATION_STEPS)
    require(
        condition=str(error.value) == "Drape target changed",
        message="A stale target must preserve its readiness message when blocking simulation.",
    )
    require(
        condition=scene.Steps == 0 and not calls,
        message="A stale target must block simulation before changing or recomputing the scene.",
    )


def test_reset_simulation_resets_scene_and_recomputes() -> None:
    """Reset the scene and recompute its document exactly once."""
    calls: list[object] = []

    def add_object(_type_name: str, _object_name: str) -> object:
        """Provide the document feature-creation operation required by the protocol."""
        return object()

    def get_object(_object_name: str) -> object | None:
        """Return no existing feature from the empty document fixture."""
        return None

    document = cast(
        "SimulationDocument",
        SimpleNamespace(
            Objects=(),
            addObject=add_object,
            getObject=get_object,
            recompute=lambda: calls.append("recompute"),
        ),
    )
    scene = cast(
        "SimulationScene",
        SimpleNamespace(Steps=0, Document=document, ClothPieces=(), Proxy=None),
    )

    def require_simulation() -> tuple[SimulationDocument, SimulationScene]:
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


def test_simulation_command_resources_and_activation_are_runtime_objects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Register and activate the public run command and inspect its FreeCAD resources.

    Args:
        monkeypatch: Fixture that registers the command against a fake FreeCAD GUI.
    """
    _app_module, scene, calls, registered = _register_workbench_commands(monkeypatch)
    command = registered["ClothSimulation_Run"]
    is_active = cast(
        "Callable[[], bool]",
        getattr(command, _FREECAD_IS_ACTIVE_METHOD),
    )
    activate = cast(
        "Callable[[], object]",
        getattr(command, _FREECAD_ACTIVATED_METHOD),
    )
    get_resources = cast(
        "Callable[[], dict[str, object]]",
        getattr(command, _FREECAD_GET_RESOURCES_METHOD),
    )
    require(
        condition=is_active(),
        message="An active simulation must enable the run command.",
    )
    require(
        condition=activate() is scene,
        message="Run-command activation must return the selected simulation scene.",
    )
    resources = get_resources()
    require(
        condition=resources["MenuText"] == "Run Simulation",
        message="The command menu text must match its configured label.",
    )
    require(
        condition=resources["ToolTip"] == "Run 30 steps of the quality-aware CPU cloth simulation",
        message="The command tooltip must match its configured description.",
    )
    require(
        condition=bool(resources["Pixmap"]),
        message="The command resources must include its icon path.",
    )
    require(
        condition=scene.Steps == DEFAULT_SIMULATION_STEPS,
        message="Run-command activation must execute the configured default step count.",
    )
    require(
        condition=calls == ["recompute", "refresh"],
        message="Run-command activation must recompute and refresh the active document.",
    )


def test_registered_simulation_command_is_inactive_without_an_active_scene(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Disable the public run command when no FreeCAD document is active.

    Args:
        monkeypatch: Fixture that registers the command against a fake FreeCAD GUI.
    """
    app_module, _scene, _calls, registered = _register_workbench_commands(monkeypatch)
    app_module.__dict__["ActiveDocument"] = None
    command = registered["ClothSimulation_Run"]
    is_active = cast(
        "Callable[[], bool]",
        getattr(command, _FREECAD_IS_ACTIVE_METHOD),
    )
    require(
        condition=not is_active(),
        message="The run command must be inactive when no simulation document exists.",
    )
