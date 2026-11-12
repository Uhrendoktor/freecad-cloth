# Copyright (C) 2026 FreeCAD Cloth contributors
"""Commands for the Cloth Simulation workbench."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING, Protocol, cast

from freecad_cloth.common.CommandAdapter import icon_for_command
from freecad_cloth.common.JsonTypes import JsonObject, JsonValue
from freecad_cloth.common.garment_document import FreeCADDocumentObjectProtocol
from freecad_cloth.simulation.simulation_protocols import SimulationDocument, SimulationScene

if TYPE_CHECKING:
    from freecad_cloth.sewing.SeamOverlay import SeamOverlayController


class _FreeCADViewObject(Protocol):
    """Viewport visibility property used when initializing the avatar."""

    Visibility: bool


class _FreeCADAvatarFeature(FreeCADDocumentObjectProtocol, Protocol):
    """Avatar feature members needed by simulation-scene setup."""

    AvatarType: str
    Label: str
    ViewObject: _FreeCADViewObject


class _PatternPieceFeature(FreeCADDocumentObjectProtocol, Protocol):
    """PatternPiece identity required when transferring pieces into a simulation."""

    PieceId: str
    PatternType: str


class _DrapeTargetFeature(FreeCADDocumentObjectProtocol, Protocol):
    """Persisted target source and readiness fields used before simulation advancement."""

    TargetType: str
    SourceObject: FreeCADDocumentObjectProtocol | None
    CollisionDeflection: float
    CollisionThickness: float
    Enabled: bool


class _SimulationQualityTaskPanel(Protocol):
    """Native task-panel actions returned by the simulation quality editor."""

    def accept(self) -> bool:
        """Accept staged quality changes."""
        ...

    def reject(self) -> bool:
        """Reject staged quality changes."""
        ...

    def getStandardButtons(self) -> int:
        """Return the native OK/Cancel button flags."""
        ...


type _SimulationResult = (
    JsonValue | FreeCADDocumentObjectProtocol | SimulationScene | _SimulationQualityTaskPanel
)


class _WorkbenchCommand(Protocol):
    """Command methods registered with the native FreeCAD GUI."""

    def Activated(self) -> _SimulationResult:
        """Run the command and return its user-visible result."""
        ...

    def GetResources(self) -> dict[str, str]:
        """Return menu, tooltip, and icon resources for the command."""
        ...

    def IsActive(self) -> bool:
        """Return whether the command is available in the active document."""
        ...


class _FreeCADGui(Protocol):
    """Minimal FreeCAD GUI command-registration API."""

    def addCommand(self, command_name: str, command: _WorkbenchCommand) -> None:
        """Register one Python workbench command.

        Args:
            command_name: Stable FreeCAD command identifier.
            command: Command object implementing the native workbench interface.
        """
        ...


def create_simulation() -> SimulationScene:
    """Create a quality-aware simulation in the active document.

    Returns:
        The newly created simulation scene.
    """
    import FreeCAD as App

    doc = cast(
        "SimulationDocument",
        App.ActiveDocument or App.newDocument("ClothSimulation"),
    )
    return create_quality_simulation_scene(doc)


def create_quality_simulation_scene(
    doc: SimulationDocument,
    *,
    avatar_source: FreeCADDocumentObjectProtocol | None = None,
    cloth_pieces: Sequence[_PatternPieceFeature] = (),
) -> SimulationScene:
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
        avatar_object = doc.getObject("ClothAvatar")
        if avatar_object is None:
            avatar_object = create_avatar(doc=doc, attach_collision=False)
        avatar = cast("_FreeCADAvatarFeature", avatar_object)
        avatar.Label = "Cloth Human Avatar (MakeHuman)"
        view = cast(
            "_FreeCADViewObject | None",
            getattr(avatar_object, "ViewObject", None),
        )
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


def create_drape_scene() -> SimulationScene:
    """Create a drape scene with its default mannequin collision target.

    Returns:
        The newly created drape simulation scene.
    """
    import FreeCAD as App

    doc = cast(
        "SimulationDocument",
        App.ActiveDocument or App.newDocument("ClothDrape"),
    )
    return create_quality_simulation_scene(doc)


def _is_simulation_scene(obj: FreeCADDocumentObjectProtocol) -> bool:
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


def _find_simulation(doc: SimulationDocument) -> SimulationScene | None:
    """Find the first simulation scene in a document.

    Args:
        doc: FreeCAD document whose object inventory is searched.

    Returns:
        The first matching simulation scene, or None when no scene exists.
    """
    return next(
        (cast("SimulationScene", obj) for obj in doc.Objects if _is_simulation_scene(obj)),
        None,
    )


def _find_drape_target(doc: SimulationDocument) -> _DrapeTargetFeature | None:
    """Find the persistent drape target in a FreeCAD document.

    Args:
        doc: FreeCAD document whose object inventory is searched.

    Returns:
        The first drape target object, or None when no target exists.
    """
    return next(
        (
            cast("_DrapeTargetFeature", obj)
            for obj in doc.Objects
            if getattr(obj, "Name", "") == "DrapeTarget"
            or getattr(obj, "TargetType", None) is not None
        ),
        None,
    )


def _require_drape_target_ready(
    doc: SimulationDocument,
    *,
    find_target: Callable[[SimulationDocument], _DrapeTargetFeature | None] | None = None,
    target_status_fn: Callable[
        [_DrapeTargetFeature | None], Mapping[str, JsonValue]
    ] | None = None,
) -> _DrapeTargetFeature | None:
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
        raise RuntimeError(str(status["message"]))
    return target


_active_simulation_quality_task_panel: _SimulationQualityTaskPanel | None = None


def get_active_simulation_quality_task_panel() -> _SimulationQualityTaskPanel | None:
    """Return the task panel opened by the public simulation controls command.

    Returns:
        The active quality task panel, or None when no panel is open.
    """
    return _active_simulation_quality_task_panel


def edit_simulation() -> _SimulationQualityTaskPanel:
    """Open the native simulation quality controls task panel.

    Returns:
        The native task-panel object displayed by FreeCAD.
    """
    global _active_simulation_quality_task_panel
    import FreeCAD as App

    from freecad_cloth.simulation.SimulationQualityGui import show_simulation_quality_task

    doc = cast("SimulationDocument | None", App.ActiveDocument)
    scene = _find_simulation(doc) if doc is not None else None
    if scene is not None:
        from freecad_cloth.simulation.SimulationQualityRuntime import ensure_quality_properties

        ensure_quality_properties(scene)
    _active_simulation_quality_task_panel = show_simulation_quality_task(scene)
    return _active_simulation_quality_task_panel


def _require_simulation() -> tuple[SimulationDocument, SimulationScene]:
    """Require an active document and an existing simulation scene.

    Returns:
        The active FreeCAD document and its selected simulation scene.

    Raises:
        RuntimeError: If no active document or simulation scene exists.
    """
    import FreeCAD as App

    doc = cast("SimulationDocument | None", App.ActiveDocument)
    if doc is None:
        msg = "no active document"
        raise RuntimeError(msg)
    scene = _find_simulation(doc)
    if scene is None:
        msg = "no Cloth Simulation object in active document"
        raise RuntimeError(msg)
    return doc, scene


def simulate_selected(steps: int | None = None) -> FreeCADDocumentObjectProtocol | SimulationScene:
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
    return cast("FreeCADDocumentObjectProtocol", panels[0]) if panels else scene


def run_simulation(
    steps: int = 30,
    *,
    simulate: Callable[[int], _SimulationResult] | None = None,
) -> _SimulationResult:
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
    require_simulation_fn: Callable[[], tuple[SimulationDocument, SimulationScene]] | None = None,
    reset_scene_fn: Callable[[SimulationScene], SimulationScene] | None = None,
    refresh_overlay_fn: Callable[
        [SimulationDocument], SeamOverlayController | None
    ] | None = None,
) -> SimulationScene:
    """Reset the active simulation state without changing its authored settings.

    Args:
        require_simulation_fn: Optional typed lookup for the active document and scene.
        reset_scene_fn: Optional state-reset callback used by headless tests.
        refresh_overlay_fn: Optional seam-overlay refresh callback used by headless tests.

    Returns:
        The reset simulation scene with its authored settings unchanged.
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

        refresh_overlay_fn = cast(
            "Callable[[SimulationDocument], SeamOverlayController | None]",
            refresh_seam_overlay,
        )
    refresh_overlay_fn(scene.Document)
    return scene


def simulation_status() -> JsonObject:
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
        fn: Callable[[], _SimulationResult],
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

    def Activated(self) -> _SimulationResult:
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

        doc = cast("SimulationDocument | None", App.ActiveDocument)
        return bool(doc is not None and _find_simulation(doc) is not None)
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

    gui = cast("_FreeCADGui", Gui)
    if callable(getattr(gui, "addCommand", None)):
        gui.addCommand(
            "ClothSimulation_Create",
            _FunctionCommand(
                create_simulation,
                "Create Simulation",
                "Create a quality-aware cloth simulation object",
                "ClothSimulation_Create",
            ),
        )
        gui.addCommand(
            "ClothSimulation_CreateDrape",
            _FunctionCommand(
                create_drape_scene,
                "Create Drape Scene",
                "Create a deterministic cloth drape scene without implicit solver steps",
                "ClothSimulation_CreateDrape",
            ),
        )
        gui.addCommand(
            "ClothSimulation_Edit",
            _FunctionCommand(
                edit_simulation,
                "Simulation Controls",
                "Open the cloth simulation quality task panel",
                "ClothSimulation_Edit",
            ),
        )
        gui.addCommand(
            "ClothSimulation_Step",
            _FunctionCommand(
                lambda: simulate_selected(),
                "Step Simulation",
                "Advance the quality-aware CPU cloth simulation",
                "ClothSimulation_Step",
                _has_simulation,
            ),
        )
        gui.addCommand(
            "ClothSimulation_Run",
            _FunctionCommand(
                run_simulation,
                "Run Simulation",
                "Run 30 steps of the quality-aware CPU cloth simulation",
                "ClothSimulation_Run",
                _has_simulation,
            ),
        )
        gui.addCommand(
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
