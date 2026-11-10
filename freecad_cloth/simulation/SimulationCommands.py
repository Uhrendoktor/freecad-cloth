# Copyright (C) 2026 FreeCAD Cloth contributors
"""Commands for the Cloth Simulation workbench."""

from collections.abc import Callable, Sequence
from typing import Protocol, cast

from freecad_cloth.common.CommandAdapter import icon_for_command


class _FreeCADDocument(Protocol):
    """Minimal FreeCAD document API used by simulation-scene creation."""

    Objects: Sequence[object]

    def getObject(self, object_name: str) -> object | None:
        """Return a document object by internal name, if present.

        Args:
            object_name: Internal FreeCAD object name to look up.

        Returns:
            The matching document object or None when it is absent.
        """
        ...

    def recompute(self) -> None:
        """Recompute derived document state after scene properties change."""
        ...


def create_simulation() -> object:
    """Create a quality-aware simulation in the active document.

    Returns:
        The newly created simulation scene.
    """
    import FreeCAD as App

    doc = App.ActiveDocument or App.newDocument("ClothSimulation")
    return create_quality_simulation_scene(doc)


def create_quality_simulation_scene(
    doc: _FreeCADDocument,
    *,
    avatar_source: object | None = None,
    cloth_pieces: Sequence[object] = (),
) -> object:
    """Create one quality-controlled simulation from the supplied source state.

    Args:
        doc: FreeCAD document that owns the simulation and its target.
        avatar_source: Optional shape or mesh to use as the collision source.
            When absent, the canonical generated mannequin is used.
        cloth_pieces: Optional pattern pieces transferred into the simulation.

    Returns:
        The quality-controlled simulation scene with a persistent drape target.
    """
    from freecad_cloth.avatar.AvatarCommands import create_avatar
    from freecad_cloth.simulation.DrapeCommands import set_drape_target_source
    from freecad_cloth.simulation.DrapeTarget import DEFAULT_MANNEQUIN_COLLISION_THICKNESS_MM
    from freecad_cloth.simulation.SimulationObjects import create_simulation_scene
    from freecad_cloth.simulation.SimulationQualityRuntime import (
        QualitySimulationProxy,
        ensure_quality_properties,
    )

    scene = create_simulation_scene(doc)
    scene.ClothPieces = list(cloth_pieces)
    if avatar_source is None:
        avatar = doc.getObject("ClothAvatar")
        if avatar is None:
            avatar = create_avatar(doc=doc, attach_collision=False)
        avatar.Label = "Cloth Human Avatar (MakeHuman)"
        view = getattr(avatar, "ViewObject", None)
        if view is not None:
            view.Visibility = True
    else:
        avatar = avatar_source

    is_mannequin = str(getattr(avatar, "AvatarType", "")) == "ClothAvatar"
    thickness_mm = DEFAULT_MANNEQUIN_COLLISION_THICKNESS_MM if is_mannequin else 2.0
    set_drape_target_source(scene, avatar, thickness_mm, 1.0)
    ensure_quality_properties(scene)
    scene.Proxy = QualitySimulationProxy()
    doc.recompute()
    return scene


def create_drape_scene() -> object:
    """Create a drape scene with its default mannequin collision target.

    Returns:
        The newly created drape simulation scene.
    """
    import FreeCAD as App

    doc = App.ActiveDocument or App.newDocument("ClothDrape")
    return create_quality_simulation_scene(doc)


def _is_simulation_scene(obj: object) -> bool:
    """Identify simulation objects by their persisted name or proxy type.

    Args:
        obj: Candidate document object from the active FreeCAD document.

    Returns:
        True when the candidate is a Cloth Simulation scene.
    """
    return (
        getattr(obj, "Name", "") == "ClothSimulation"
        or getattr(getattr(obj, "Proxy", None), "Type", "") == "ClothSimulation"
    )


def _find_simulation(doc: _FreeCADDocument) -> object | None:
    """Find the first simulation scene in a document.

    Args:
        doc: FreeCAD document whose object inventory is searched.

    Returns:
        The first matching simulation scene, or None when no scene exists.
    """
    return next((obj for obj in doc.Objects if _is_simulation_scene(obj)), None)


def _find_drape_target(doc: _FreeCADDocument) -> object | None:
    """Find the persistent drape target in a FreeCAD document.

    Args:
        doc: FreeCAD document whose object inventory is searched.

    Returns:
        The first drape target object, or None when no target exists.
    """
    return next(
        (
            obj
            for obj in doc.Objects
            if getattr(obj, "Name", "") == "DrapeTarget"
            or getattr(obj, "TargetType", None) is not None
        ),
        None,
    )


def _require_drape_target_ready(
    doc: _FreeCADDocument,
    *,
    find_target: Callable[..., object | None] | None = None,
    target_status_fn: Callable[..., dict[str, str]] | None = None,
) -> object | None:
    """Reject simulation advancement when its persisted drape target is stale.

    Args:
        doc: FreeCAD document containing the selected simulation and target.
        find_target: Optional document lookup used by headless tests.
        target_status_fn: Optional target-state evaluator used by headless tests.

    Returns:
        The target whose status permits simulation advancement.

    Raises:
        RuntimeError: If the target is missing, stale, or otherwise not ready.
    """
    if find_target is None:
        find_target = _find_drape_target
    if target_status_fn is None:
        from freecad_cloth.simulation.DrapeTarget import target_status

        target_status_fn = target_status

    target = find_target(doc)
    status = target_status_fn(target)
    if status["state"] != "ready":
        raise RuntimeError(status["message"])
    return target


_ACTIVE_SIMULATION_QUALITY_TASK_PANEL = None


def get_active_simulation_quality_task_panel():
    """Return the task panel opened by the public simulation controls command."""
    return _ACTIVE_SIMULATION_QUALITY_TASK_PANEL


def edit_simulation():
    """Open the native simulation quality controls task panel."""
    global _ACTIVE_SIMULATION_QUALITY_TASK_PANEL
    import FreeCAD as App

    from freecad_cloth.simulation.SimulationQualityGui import show_simulation_quality_task
    from freecad_cloth.simulation.SimulationQualityRuntime import ensure_quality_properties

    doc = App.ActiveDocument
    scene = _find_simulation(doc) if doc else None
    if scene is not None:
        ensure_quality_properties(scene)
    _ACTIVE_SIMULATION_QUALITY_TASK_PANEL = show_simulation_quality_task(scene)
    return _ACTIVE_SIMULATION_QUALITY_TASK_PANEL


class _SimulationScene(Protocol):
    """Document-backed scene fields required by public simulation controls."""

    Steps: int


def _require_simulation() -> tuple[_FreeCADDocument, _SimulationScene]:
    """Require an active document and an existing simulation scene.

    Returns:
        The active FreeCAD document and its selected simulation scene.

    Raises:
        RuntimeError: If no active document or simulation scene exists.
    """
    import FreeCAD as App

    doc = App.ActiveDocument
    if doc is None:
        msg = "no active document"
        raise RuntimeError(msg)
    scene = _find_simulation(doc)
    if scene is None:
        msg = "no Cloth Simulation object in active document"
        raise RuntimeError(msg)
    return cast("_FreeCADDocument", doc), cast("_SimulationScene", scene)


def simulate_selected(steps: int | None = None) -> object:
    """Advance the selected native simulation through its document proxy.

    Args:
        steps: Optional number of solver steps; defaults to one step.

    Returns:
        The first generated drape panel, or the simulation scene when no panel exists.

    Raises:
        ValueError: If the requested step count is less than one.
    """
    doc, scene = _require_simulation()
    _require_drape_target_ready(doc)
    count = int(steps if steps is not None else 1)
    if count < 1:
        msg = "steps must be positive"
        raise ValueError(msg)
    scene.Steps = int(scene.Steps) + count
    doc.recompute()
    from freecad_cloth.sewing.SeamOverlay import refresh_seam_overlay

    refresh_seam_overlay(doc)
    panels = tuple(getattr(scene, "DrapePanels", ()))
    return panels[0] if panels else scene


def run_simulation(
    steps: int = 30,
    *,
    simulate: Callable[..., object] | None = None,
) -> object:
    """Run an explicit batch of simulation steps on the active scene.

    Args:
        steps: Number of simulation steps to delegate; defaults to thirty.
        simulate: Optional simulation callback used by headless tests.

    Returns:
        The object returned by the selected simulation callback.
    """
    run_selected = simulate_selected if simulate is None else simulate
    return run_selected(steps)


def reset_simulation(
    *,
    require_simulation_fn: Callable[[], tuple[object, object]] | None = None,
    reset_scene_fn: Callable[[object], object] | None = None,
    refresh_overlay_fn: Callable[[object], object] | None = None,
):
    """Reset the active simulation state without changing its authored settings.

    Args:
        require_simulation_fn: Optional active-scene lookup used by headless tests.
        reset_scene_fn: Optional state-reset callback used by headless tests.
        refresh_overlay_fn: Optional seam-overlay refresh callback used by headless tests.
    """
    require_simulation = (
        _require_simulation if require_simulation_fn is None else require_simulation_fn
    )
    _doc, scene = require_simulation()
    if reset_scene_fn is None:
        from freecad_cloth.simulation.SimulationObjects import reset_scene

        reset_scene_fn = reset_scene
    reset_scene_fn(scene)
    scene.Document.recompute()
    if refresh_overlay_fn is None:
        from freecad_cloth.sewing.SeamOverlay import refresh_seam_overlay

        refresh_overlay_fn = refresh_seam_overlay
    refresh_overlay_fn(scene.Document)
    return scene


def simulation_status():
    """Return a deterministic, UI-friendly lifecycle/status summary."""
    try:
        doc, scene = _require_simulation()
    except RuntimeError as exc:
        return {
            "state": "unavailable",
            "message": str(exc),
            "steps": 0,
            "particles": 0,
            "time": 0.0,
            "target_state": "missing",
            "target_message": "No drape target selected",
            "target_stale": True,
            "target_reason": "target missing",
        }
    finite = bool(getattr(scene, "FiniteState", True))
    target = _find_drape_target(doc)
    from freecad_cloth.simulation.DrapeTarget import target_status

    target_info = target_status(target)
    target_info = {
        "blocked": target_info["state"]
        in {"stale", "unbuilt", "unassigned", "invalid", "missing", "disabled"},
        **target_info,
    }
    return {
        "state": "ready" if finite and not target_info["blocked"] else "invalid/stale",
        "message": "Cloth Simulation ready"
        if finite and not target_info["blocked"]
        else target_info["message"],
        "steps": int(getattr(scene, "Steps", 0)),
        "particles": int(getattr(scene, "ParticleCount", 0)),
        "time": float(getattr(scene, "SimulatedTime", 0.0)),
        "target_state": target_info["state"],
        "target_message": target_info["message"],
        "target_stale": bool(target_info["stale"]),
        "target_reason": target_info["reason"],
    }


class _FunctionCommand:
    """Adapt a Python callback to FreeCAD's workbench command interface."""

    def __init__(
        self,
        fn: Callable[[], object],
        text: str,
        tip: str,
        command_name: str,
        active: Callable[[], bool] | None = None,
    ) -> None:
        """Store the action and presentation metadata for one FreeCAD command.

        Args:
            fn: Callback invoked when the command is activated.
            text: Menu label shown for the command.
            tip: Tooltip shown by the FreeCAD toolbar.
            command_name: Stable command identifier used to select its icon.
            active: Optional predicate controlling whether the command is enabled.
        """
        self.fn, self.text, self.tip, self.command_name, self.active = (
            fn,
            text,
            tip,
            command_name,
            active,
        )

    def Activated(self) -> object:
        """Invoke the registered command action.

        Returns:
            Result returned by the command callback.
        """
        return self.fn()

    def GetResources(self) -> dict[str, str]:
        """Return the menu, tooltip, and icon metadata for FreeCAD.

        Returns:
            FreeCAD command resource fields.
        """
        return {
            "MenuText": self.text,
            "ToolTip": self.tip,
            "Pixmap": icon_for_command(self.command_name),
        }

    def IsActive(self) -> bool:
        """Report whether the command is available for the current document.

        Returns:
            True when no active-state predicate is configured or it accepts the scene.
        """
        return bool(self.active()) if self.active is not None else True


def _has_simulation() -> bool:
    """Return whether the active FreeCAD document contains a simulation scene.

    Returns:
        True when a simulation scene is present; otherwise False.
    """
    try:
        import FreeCAD as App

        return bool(App.ActiveDocument and _find_simulation(App.ActiveDocument) is not None)
    except (ImportError, AttributeError):
        return False


COMMANDS = [
    "ClothSimulation_Create",
    "ClothSimulation_CreateDrape",
    "ClothSimulation_Edit",
    "ClothSimulation_Step",
    "ClothSimulation_Run",
    "ClothSimulation_Reset",
]

try:
    import FreeCADGui as Gui

    if hasattr(Gui, "addCommand"):
        Gui.addCommand(
            "ClothSimulation_Create",
            _FunctionCommand(
                create_simulation,
                "Create Simulation",
                "Create a quality-aware cloth simulation object",
                "ClothSimulation_Create",
            ),
        )
        Gui.addCommand(
            "ClothSimulation_CreateDrape",
            _FunctionCommand(
                create_drape_scene,
                "Create Drape Scene",
                "Create a deterministic cloth drape scene without implicit solver steps",
                "ClothSimulation_CreateDrape",
            ),
        )
        Gui.addCommand(
            "ClothSimulation_Edit",
            _FunctionCommand(
                edit_simulation,
                "Simulation Controls",
                "Open the cloth simulation quality task panel",
                "ClothSimulation_Edit",
            ),
        )
        Gui.addCommand(
            "ClothSimulation_Step",
            _FunctionCommand(
                lambda: simulate_selected(),
                "Step Simulation",
                "Advance the quality-aware CPU cloth simulation",
                "ClothSimulation_Step",
                _has_simulation,
            ),
        )
        Gui.addCommand(
            "ClothSimulation_Run",
            _FunctionCommand(
                run_simulation,
                "Run Simulation",
                "Run 30 steps of the quality-aware CPU cloth simulation",
                "ClothSimulation_Run",
                _has_simulation,
            ),
        )
        Gui.addCommand(
            "ClothSimulation_Reset",
            _FunctionCommand(
                reset_simulation,
                "Reset Simulation",
                "Reset simulation state while retaining authored settings",
                "ClothSimulation_Reset",
                _has_simulation,
            ),
        )
except (ImportError, AttributeError):
    pass
