# Copyright (C) 2026 FreeCAD Cloth contributors
"""Typed FreeCAD UI handoff between Simulation and the existing fitting stage.

The persisted FittingScene remains the fitting-stage authority. This bridge
copies authored garment pieces from Simulation and carries the same persisted
DrapeTarget into fitting, preserving home placements and reset behavior.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Protocol, cast

from freecad_cloth.common.CommandAdapter import register_commands

if TYPE_CHECKING:
    from collections.abc import Sequence

    from freecad_cloth.common.CommandAdapter import CommandCallable, GuiCommandRegistrar


_FREECAD_COLLISION_THICKNESS_MM = 2.0
_COLLISION_DEFLECTION_MM = 1.0


class _FreeCADDocument(Protocol):
    """Describe the document members used by the fitting handoff."""

    Objects: Sequence[object]

    def recompute(self) -> None:
        """Recompute the active document."""
        ...


class _FreeCADApplication(Protocol):
    """Describe the application data used to resolve an active document."""

    ActiveDocument: _FreeCADDocument | None


class _FreeCADGui(Protocol):
    """Describe the dynamic GUI objects used by the fitting handoff."""

    Selection: object
    Control: object


class _DrapeTarget(Protocol):
    """Describe collision settings on the persisted drape target."""

    CollisionDeflection: float
    CollisionThickness: float


class _FittingScene(Protocol):
    """Describe mutable fields on a persisted fitting scene."""

    AvatarProxy: object | None
    ArrangementPoints: Sequence[object]
    DrapeTarget: object | None
    FitStatus: str
    HomePlacements: Sequence[object]
    PatternPieces: Sequence[object]
    PiecePlacements: Sequence[object]


class _SimulationScene(Protocol):
    """Describe the simulation fields consumed or updated by this bridge."""

    ClothPieces: Sequence[object]
    Document: _FreeCADDocument | None
    DrapeTarget: object | None


def _runtime_attribute(target: object, name: str) -> object:
    """Read a member dynamically exposed by a FreeCAD runtime object.

    Args:
        target: Runtime object that owns the requested member.
        name: Exact attribute spelling supplied by FreeCAD.

    Returns:
        The requested runtime value.
    """
    return getattr(target, name)


def _document_object(doc: _FreeCADDocument, name: str) -> object | None:
    """Resolve a named object using FreeCAD's dynamic document API.

    Args:
        doc: Document that owns the object.
        name: Internal document object name to find.

    Returns:
        The matching document object, or None when it is absent.
    """
    get_object = cast(
        "Callable[[str], object | None]",
        _runtime_attribute(doc, "getObject"),
    )
    return get_object(name)


def _new_document(app: _FreeCADApplication, name: str) -> _FreeCADDocument:
    """Create a document through FreeCAD's dynamically exposed application API.

    Args:
        app: FreeCAD application module.
        name: Internal name for the new document.

    Returns:
        The newly created document.
    """
    new_document = cast(
        "Callable[[str], _FreeCADDocument]",
        _runtime_attribute(app, "newDocument"),
    )
    return new_document(name)


def _selected_objects(gui: _FreeCADGui) -> Sequence[object]:
    """Read the current FreeCAD selection.

    Args:
        gui: FreeCAD GUI module.

    Returns:
        Objects currently selected in the active document.
    """
    selection = _runtime_attribute(gui, "Selection")
    get_selection = cast(
        "Callable[[], Sequence[object]]",
        _runtime_attribute(selection, "getSelection"),
    )
    return get_selection()


def _clear_selection(gui: _FreeCADGui) -> None:
    """Clear FreeCAD's current GUI selection.

    Args:
        gui: FreeCAD GUI module whose selection should be cleared.
    """
    selection = _runtime_attribute(gui, "Selection")
    clear_selection = cast(
        "Callable[[], None]",
        _runtime_attribute(selection, "clearSelection"),
    )
    clear_selection()


def _add_selection(gui: _FreeCADGui, obj: object) -> None:
    """Add one document object to FreeCAD's GUI selection.

    Args:
        gui: FreeCAD GUI module.
        obj: Document object to add to the selection.
    """
    selection = _runtime_attribute(gui, "Selection")
    add_selection = cast(
        "Callable[[object], None]",
        _runtime_attribute(selection, "addSelection"),
    )
    add_selection(obj)


def _active_dialog(gui: _FreeCADGui) -> object | None:
    """Return the task panel currently controlled by FreeCAD.

    Args:
        gui: FreeCAD GUI module.

    Returns:
        The current task panel, or None when no task panel is active.
    """
    control = _runtime_attribute(gui, "Control")
    active_dialog = cast(
        "Callable[[], object | None]",
        _runtime_attribute(control, "activeDialog"),
    )
    return active_dialog()


def _close_dialog(gui: _FreeCADGui) -> None:
    """Close FreeCAD's active task panel.

    Args:
        gui: FreeCAD GUI module whose active task panel should be closed.
    """
    control = _runtime_attribute(gui, "Control")
    close_dialog = cast(
        "Callable[[], None]",
        _runtime_attribute(control, "closeDialog"),
    )
    close_dialog()


def _activate_workbench(gui: _FreeCADGui, name: str) -> None:
    """Activate a registered FreeCAD workbench.

    Args:
        gui: FreeCAD GUI module.
        name: Stable identifier of the workbench to activate.
    """
    activate_workbench = cast(
        "Callable[[str], None]",
        _runtime_attribute(gui, "activateWorkbench"),
    )
    activate_workbench(name)


def _fitting_scene(doc: _FreeCADDocument | None) -> _FittingScene | None:
    """Find the document's persisted fitting scene.

    Args:
        doc: Document to inspect, or None when no document is active.

    Returns:
        The matching fitting scene, or None when no scene exists.
    """
    if doc is None:
        return None
    for candidate in doc.Objects:
        if getattr(candidate, "FittingType", "") == "FittingScene":
            return cast("_FittingScene", candidate)
    return None


def assign_avatar_source(source: object | None = None) -> object:
    """Assign selected geometry as the fitting scene's collision target.

    Args:
        source: Body or mesh to assign, or None to use the active GUI selection.

    Returns:
        The fitting scene updated with the assigned avatar and collision target.

    Raises:
        ValueError: If no supported body or mesh is selected.
    """
    app = cast("_FreeCADApplication", import_module("FreeCAD"))
    gui = cast("_FreeCADGui", import_module("FreeCADGui"))
    fitting_commands = import_module("freecad_cloth.avatar.FittingCommands")
    drape_target_api = import_module("freecad_cloth.simulation.DrapeTarget")

    doc = app.ActiveDocument or _new_document(app, "ClothSewing")
    scene = _fitting_scene(doc)
    if scene is None:
        scene = cast("_FittingScene", fitting_commands.create_fitting_scene())
    if source is None:
        source = next(
            (
                obj
                for obj in _selected_objects(gui)
                if hasattr(obj, "Shape") or hasattr(obj, "Mesh")
            ),
            None,
        )
    if source is None:
        msg = "select a FreeCAD body or mesh to use as the avatar source"
        raise ValueError(msg)

    target = _document_object(doc, "DrapeTarget")
    target_type = (
        "Mannequin"
        if str(getattr(source, "AvatarType", "")) == "ClothAvatar"
        else "FreeCAD Geometry"
    )
    mannequin_thickness = drape_target_api.DEFAULT_MANNEQUIN_COLLISION_THICKNESS_MM
    target_thickness = (
        mannequin_thickness if target_type == "Mannequin" else _FREECAD_COLLISION_THICKNESS_MM
    )
    if target is None:
        drape_target_api.create_drape_target(
            doc,
            source,
            target_type,
            _COLLISION_DEFLECTION_MM,
            target_thickness,
        )
    else:
        drape_target = cast("_DrapeTarget", target)
        drape_target.CollisionDeflection = _COLLISION_DEFLECTION_MM
        drape_target.CollisionThickness = target_thickness
        drape_target_api.assign_drape_target(drape_target, source, target_type)

    scene.AvatarProxy = source
    scene.FitStatus = "Avatar assigned"
    doc.recompute()
    return scene


def create_simulation_from_fitting() -> object:
    """Create a simulation scene from authored fitting pieces and avatar target.

    Returns:
        The new simulation scene containing the fitting scene's pieces.

    Raises:
        ValueError: If the document has no fitting scene or the scene has no pieces.
    """
    app = cast("_FreeCADApplication", import_module("FreeCAD"))
    simulation_objects = import_module("freecad_cloth.simulation.SimulationObjects")
    doc = app.ActiveDocument or _new_document(app, "ClothSewing")
    scene = _fitting_scene(doc)
    if scene is None:
        msg = "create a fitting scene first"
        raise ValueError(msg)
    pieces = tuple(scene.PatternPieces)
    if not pieces:
        msg = "add at least one pattern piece to the fitting scene"
        raise ValueError(msg)

    simulation = cast(
        "_SimulationScene",
        simulation_objects.create_simulation_scene(doc),
    )
    simulation.ClothPieces = list(pieces)
    avatar_proxy = scene.AvatarProxy
    if avatar_proxy is not None:
        simulation_objects.set_avatar_collision_source(
            simulation,
            avatar_proxy,
            thickness=_FREECAD_COLLISION_THICKNESS_MM,
            deflection=_COLLISION_DEFLECTION_MM,
        )
    doc.recompute()
    return simulation


FITTING_HANDOFF_COMMAND_HANDLERS: dict[str, CommandCallable] = {
    "ClothFitting_AssignAvatar": assign_avatar_source,
    "ClothFitting_CreateSimulation": create_simulation_from_fitting,
}


def register_fitting_handoff_commands(gui: object) -> None:
    """Register the simulation-owned fitting commands in FreeCAD's GUI.

    Args:
        gui: FreeCAD GUI module or an object exposing the addCommand API.
    """
    register_commands(
        cast("GuiCommandRegistrar", gui),
        FITTING_HANDOFF_COMMAND_HANDLERS,
    )


def fitting_stage_status(simulation: object | None) -> tuple[str, bool]:
    """Return the visible fitting state and whether Reset is available.

    Args:
        simulation: Simulation scene to inspect, or None when unselected.

    Returns:
        A message and a flag indicating whether saved home placements exist.
    """
    if simulation is None:
        return "No simulation scene selected.", False
    simulation_scene = cast("_SimulationScene", simulation)
    fitting = _fitting_scene(simulation_scene.Document)
    if fitting is None:
        return "Not arranged yet — use Arrange / Fit… to open the fitting stage.", False

    pieces = len(tuple(fitting.PatternPieces))
    placements = len(tuple(fitting.PiecePlacements))
    points = len(tuple(fitting.ArrangementPoints))
    state = fitting.FitStatus or "Unassigned"
    noun = "piece" if pieces == 1 else "pieces"
    message = (
        f"{state} | {pieces} {noun} assigned | {placements}/{pieces} saved placement(s) "
        f"| {points} arrangement point(s)"
    )
    return message, bool(tuple(fitting.HomePlacements))


def open_arrange_fit_from_simulation(simulation: object) -> object:
    """Open the existing fitting stage for a simulation's pieces and target.

    Args:
        simulation: Simulation scene whose pieces and drape target are handed off.

    Returns:
        The fitting scene shown in the Arrange / Fit workbench.

    Raises:
        RuntimeError: If no active document exists.
    """
    app = cast("_FreeCADApplication", import_module("FreeCAD"))
    gui = cast("_FreeCADGui", import_module("FreeCADGui"))
    fitting_commands = import_module("freecad_cloth.avatar.FittingCommands")
    simulation_scene = cast("_SimulationScene", simulation)
    doc = simulation_scene.Document or app.ActiveDocument
    if doc is None:
        msg = "open a document before opening Arrange / Fit"
        raise RuntimeError(msg)

    fitting = cast("_FittingScene", fitting_commands.create_fitting_scene())
    target = simulation_scene.DrapeTarget
    if target is not None:
        fitting.DrapeTarget = target
    pieces = tuple(simulation_scene.ClothPieces)
    if pieces:
        _clear_selection(gui)
        for piece in pieces:
            _add_selection(gui, piece)
        fitting_commands.add_selected_pattern_pieces()
    _clear_selection(gui)
    _add_selection(gui, fitting)
    if _active_dialog(gui):
        _close_dialog(gui)
    _activate_workbench(gui, "ClothSewingWorkbench")
    doc.recompute()
    return fitting


def reset_arrangement_from_simulation() -> object:
    """Reset the existing fitting scene to its saved home placements.

    Returns:
        The result from the fitting-stage reset command.
    """
    fitting_commands = import_module("freecad_cloth.avatar.FittingCommands")
    return fitting_commands.reset_arrangement()
