# Copyright (C) 2026 FreeCAD Cloth contributors
"""Typed FreeCAD UI handoff between Simulation and the existing fitting stage.

The persisted FittingScene remains the fitting-stage authority for garment
placements. This bridge resolves the document-level DrapeTarget directly and
preserves home placements and reset behavior.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, cast

from freecad_cloth.common.CommandAdapter import register_commands
from freecad_cloth.common.garment_document import FreeCADDocumentObjectProtocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from freecad_cloth.common.CommandAdapter import CommandCallable, GuiCommandRegistrar


_FREECAD_COLLISION_THICKNESS_MM = 2.0
_COLLISION_DEFLECTION_MM = 1.0


class _FreeCADDocument(Protocol):
    """Describe the document methods used by the fitting handoff."""

    Objects: Sequence[FreeCADDocumentObjectProtocol]

    def getObject(self, name: str) -> FreeCADDocumentObjectProtocol | None:
        """Look up a native document feature by its internal name."""
        ...

    def recompute(self) -> None:
        """Recompute the active document."""
        ...


class _FreeCADApplication(Protocol):
    """Describe the application methods used to resolve FreeCAD documents."""

    ActiveDocument: _FreeCADDocument | None

    def newDocument(self, name: str) -> _FreeCADDocument:
        """Create a FreeCAD document with the supplied internal name."""
        ...


class _FreeCADSelection(Protocol):
    """Describe the selection operations used by the fitting handoff."""

    def getSelection(self) -> Sequence[FreeCADDocumentObjectProtocol]:
        """Return the native features selected in the active document."""
        ...

    def clearSelection(self) -> None:
        """Clear the current selection."""
        ...

    def addSelection(self, obj: FreeCADDocumentObjectProtocol) -> None:
        """Add one native document feature to the current selection."""
        ...


class _TaskPanelDialog(Protocol):
    """Truth-testable task-panel dialog returned by FreeCAD's control API."""

    def __bool__(self) -> bool:
        """Return whether a task-panel dialog is currently active."""
        ...


class _FreeCADControl(Protocol):
    """Describe the active task-panel operations exposed by FreeCAD."""

    def activeDialog(self) -> _TaskPanelDialog | None:
        """Return the current task-panel dialog, if one exists."""
        ...

    def closeDialog(self) -> None:
        """Close the active task panel."""
        ...


class _FreeCADGui(Protocol):
    """Describe the direct GUI methods used by the fitting handoff."""

    Selection: _FreeCADSelection
    Control: _FreeCADControl

    def activateWorkbench(self, name: str) -> None:
        """Activate the registered workbench with this identifier."""
        ...


class _NativeVector(Protocol):
    """Translation coordinates used by persisted pattern-piece placements."""

    x: float
    y: float
    z: float


class _NativeRotation(Protocol):
    """Rotation data used by persisted pattern-piece placements."""

    Angle: float
    Axis: _NativeVector


class _NativePlacement(Protocol):
    """Native placement fields exposed by FreeCAD document features."""

    Base: _NativeVector
    Rotation: _NativeRotation


class _PatternPiece(FreeCADDocumentObjectProtocol, Protocol):
    """Native Sketcher PatternPiece fields shared by fitting and simulation."""

    PieceId: str
    PatternType: str
    Placement: _NativePlacement


class _DrapeTarget(FreeCADDocumentObjectProtocol, Protocol):
    """Persisted collision source and settings on the drape target."""

    CollisionDeflection: float
    CollisionThickness: float
    SourceObject: FreeCADDocumentObjectProtocol | None


class _FittingScene(Protocol):
    """Describe mutable fields on a persisted fitting scene."""

    ArrangementPoints: Sequence[str]
    FitStatus: str
    HomePlacements: Sequence[str]
    PatternPieces: Sequence[_PatternPiece]
    PiecePlacements: Sequence[str]


class _SimulationScene(Protocol):
    """Describe the simulation fields consumed or updated by this bridge."""

    ClothPieces: Sequence[_PatternPiece]
    Document: _FreeCADDocument | None
    DrapeTarget: _DrapeTarget | None


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


def assign_avatar_source(
    source: FreeCADDocumentObjectProtocol | None = None,
) -> _FittingScene:
    """Assign selected geometry as the fitting scene's collision target.

    Args:
        source: Body or mesh to assign, or None to use the active GUI selection.

    Returns:
        The fitting scene updated with the assigned avatar and collision target.

    Raises:
        ValueError: If no supported body or mesh is selected.
    """
    import FreeCAD as App
    import FreeCADGui as Gui

    from freecad_cloth.avatar import FittingCommands as fitting_commands
    from freecad_cloth.simulation import DrapeTarget as drape_target_api

    app = cast("_FreeCADApplication", App)
    gui = cast("_FreeCADGui", Gui)

    doc = app.ActiveDocument or app.newDocument("ClothSewing")
    scene = _fitting_scene(doc)
    if scene is None:
        scene = cast("_FittingScene", fitting_commands.create_fitting_scene())
    if source is None:
        source = next(
            (
                obj
                for obj in gui.Selection.getSelection()
                if hasattr(obj, "Shape") or hasattr(obj, "Mesh")
            ),
            None,
        )
    if source is None:
        msg = "select a FreeCAD body or mesh to use as the avatar source"
        raise ValueError(msg)

    target = doc.getObject("DrapeTarget")
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

    scene.FitStatus = "Avatar assigned"
    doc.recompute()
    return scene


def create_simulation_from_fitting() -> _SimulationScene:
    """Create a simulation scene from authored fitting pieces and avatar target.

    Returns:
        The new simulation scene containing the fitting scene's pieces.

    Raises:
        ValueError: If the document has no fitting scene or the scene has no pieces.
    """
    import FreeCAD as App

    from freecad_cloth.simulation import SimulationObjects as simulation_objects

    app = cast("_FreeCADApplication", App)
    doc = app.ActiveDocument or app.newDocument("ClothSewing")
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
    doc_target = doc.getObject("DrapeTarget")
    avatar_source = getattr(doc_target, "SourceObject", None)
    if avatar_source is not None:
        from freecad_cloth.simulation.DrapeCommands import set_drape_target_source

        set_drape_target_source(
            simulation,
            avatar_source,
            thickness=_FREECAD_COLLISION_THICKNESS_MM,
            deflection=_COLLISION_DEFLECTION_MM,
        )
    doc.recompute()
    return simulation


FITTING_HANDOFF_COMMAND_HANDLERS: dict[str, CommandCallable] = {
    "ClothFitting_AssignAvatar": assign_avatar_source,
    "ClothFitting_CreateSimulation": create_simulation_from_fitting,
}


def register_fitting_handoff_commands(gui: GuiCommandRegistrar) -> None:
    """Register the simulation-owned fitting commands in FreeCAD's GUI.

    Args:
        gui: FreeCAD GUI module or an object exposing the addCommand API.
    """
    register_commands(
        cast("GuiCommandRegistrar", gui),
        FITTING_HANDOFF_COMMAND_HANDLERS,
    )


def fitting_stage_status(simulation: _SimulationScene | None) -> tuple[str, bool]:
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


def open_arrange_fit_from_simulation(simulation: _SimulationScene) -> _FittingScene:
    """Open the existing fitting stage for a simulation's pieces and target.

    Args:
        simulation: Simulation scene whose pieces and drape target are handed off.

    Returns:
        The fitting scene shown in the Arrange / Fit workbench.

    Raises:
        RuntimeError: If no active document exists.
    """
    import FreeCAD as App
    import FreeCADGui as Gui

    from freecad_cloth.avatar import FittingCommands as fitting_commands

    app = cast("_FreeCADApplication", App)
    gui = cast("_FreeCADGui", Gui)
    simulation_scene = cast("_SimulationScene", simulation)
    doc = simulation_scene.Document or app.ActiveDocument
    if doc is None:
        msg = "open a document before opening Arrange / Fit"
        raise RuntimeError(msg)

    fitting = cast("_FittingScene", fitting_commands.create_fitting_scene())
    pieces = tuple(simulation_scene.ClothPieces)
    if pieces:
        gui.Selection.clearSelection()
        for piece in pieces:
            gui.Selection.addSelection(piece)
        fitting_commands.add_selected_pattern_pieces()
    gui.Selection.clearSelection()
    gui.Selection.addSelection(fitting)
    if gui.Control.activeDialog():
        gui.Control.closeDialog()
    gui.activateWorkbench("ClothSewingWorkbench")
    doc.recompute()
    return fitting


def reset_arrangement_from_simulation() -> _FittingScene:
    """Reset the existing fitting scene to its saved home placements.

    Returns:
        The result from the fitting-stage reset command.
    """
    from freecad_cloth.avatar import FittingCommands as fitting_commands

    return fitting_commands.reset_arrangement()
