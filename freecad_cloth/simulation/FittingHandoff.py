# Copyright (C) 2026 FreeCAD Cloth contributors
"""Native UI handoff from Simulation to the existing Cloth fitting stage.

The persistent FittingScene remains the fitting-stage authority. This bridge
copies only the already-authored garment pieces from Simulation and carries the
same persistent DrapeTarget into fitting, preserving HomePlacements/Reset.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import cast

from freecad_cloth.common.CommandAdapter import GuiCommandRegistrar, register_commands

_FREECAD_COLLISION_THICKNESS_MM = 2.0
_COLLISION_DEFLECTION_MM = 1.0


def assign_avatar_source(source: object | None = None) -> object:
    """Assign selected geometry as the persistent fitting scene's collision target.

    Args:
        source: Body or mesh to assign, or None to use the active GUI selection.

    Returns:
        The fitting scene updated with the assigned avatar and collision target.

    Raises:
        ValueError: If no supported body or mesh is selected.
    """
    import FreeCAD as App
    import FreeCADGui as Gui

    from freecad_cloth.avatar import FittingCommands
    from freecad_cloth.simulation.DrapeTarget import (
        DEFAULT_MANNEQUIN_COLLISION_THICKNESS_MM,
        assign_drape_target,
        create_drape_target,
    )

    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    scene = _fitting_scene(doc)
    if scene is None:
        scene = FittingCommands.create_fitting_scene()
    if source is None:
        source = next(
            (obj for obj in Gui.Selection.getSelection() if hasattr(obj, "Shape") or hasattr(obj, "Mesh")),
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
    target_thickness = (
        DEFAULT_MANNEQUIN_COLLISION_THICKNESS_MM
        if target_type == "Mannequin"
        else _FREECAD_COLLISION_THICKNESS_MM
    )
    if target is None:
        target = create_drape_target(
            doc,
            source,
            target_type,
            _COLLISION_DEFLECTION_MM,
            target_thickness,
        )
    else:
        target.CollisionDeflection = _COLLISION_DEFLECTION_MM
        target.CollisionThickness = target_thickness
        assign_drape_target(target, source, target_type)

    setattr(scene, "AvatarProxy", source)
    setattr(scene, "FitStatus", "Avatar assigned")
    doc.recompute()
    return scene


def create_simulation_from_fitting() -> object:
    """Create a simulation scene from authored fitting pieces and avatar target.

    Returns:
        The new simulation scene containing the fitting scene's pieces.

    Raises:
        ValueError: If the document has no fitting scene or the scene has no pieces.
    """
    import FreeCAD as App

    from freecad_cloth.simulation.SimulationObjects import (
        create_simulation_scene,
        set_avatar_collision_source,
    )

    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    scene = _fitting_scene(doc)
    if scene is None:
        msg = "create a fitting scene first"
        raise ValueError(msg)
    pieces = tuple(getattr(scene, "PatternPieces", ()) or ())
    if not pieces:
        msg = "add at least one pattern piece to the fitting scene"
        raise ValueError(msg)

    simulation = create_simulation_scene(doc)
    setattr(simulation, "ClothPieces", list(pieces))
    avatar_proxy = getattr(scene, "AvatarProxy", None)
    if avatar_proxy is not None:
        set_avatar_collision_source(
            simulation,
            avatar_proxy,
            thickness=_FREECAD_COLLISION_THICKNESS_MM,
            deflection=_COLLISION_DEFLECTION_MM,
        )
    doc.recompute()
    return simulation


FITTING_HANDOFF_COMMAND_HANDLERS: dict[str, Callable[[], object]] = {
    "ClothFitting_AssignAvatar": assign_avatar_source,
    "ClothFitting_CreateSimulation": create_simulation_from_fitting,
}


def register_fitting_handoff_commands(gui: object) -> None:
    """Register the simulation-owned fitting handoff commands in FreeCAD's GUI.

    Args:
        gui: FreeCAD GUI module or an object exposing the addCommand API.
    """
    register_commands(cast(GuiCommandRegistrar, gui), FITTING_HANDOFF_COMMAND_HANDLERS)



def _fitting_scene(doc):
    return next(
        (
            obj
            for obj in getattr(doc, "Objects", ())
            if getattr(obj, "FittingType", "") == "FittingScene"
        ),
        None,
    )


def fitting_stage_status(simulation):
    """Return visible fitting state plus whether Reset arrangement is available."""
    if simulation is None:
        return "No simulation scene selected.", False
    doc = getattr(simulation, "Document", None)
    fitting = _fitting_scene(doc) if doc is not None else None
    if fitting is None:
        return "Not arranged yet — use Arrange / Fit… to open the fitting stage.", False
    pieces = len(tuple(getattr(fitting, "PatternPieces", ()) or ()))
    placements = len(tuple(getattr(fitting, "PiecePlacements", ()) or ()))
    points = len(tuple(getattr(fitting, "ArrangementPoints", ()) or ()))
    state = str(getattr(fitting, "FitStatus", "Unassigned"))
    noun = "piece" if pieces == 1 else "pieces"
    message = "%s | %d %s assigned | %d/%d saved placement(s) | %d arrangement point(s)" % (
        state,
        pieces,
        noun,
        placements,
        pieces,
        points,
    )
    return message, bool(tuple(getattr(fitting, "HomePlacements", ()) or ()))


def open_arrange_fit_from_simulation(simulation):
    """Open the existing fitting stage for the simulation's pieces and target."""
    import FreeCAD as App
    import FreeCADGui as Gui

    doc = getattr(simulation, "Document", None) or App.ActiveDocument
    if doc is None:
        msg = "open a document before opening Arrange / Fit"
        raise RuntimeError(msg)
    from freecad_cloth.avatar import FittingCommands

    fitting = FittingCommands.create_fitting_scene()
    target = getattr(simulation, "DrapeTarget", None)
    if target is not None:
        fitting.DrapeTarget = target
    pieces = tuple(getattr(simulation, "ClothPieces", ()) or ())
    if pieces:
        Gui.Selection.clearSelection()
        for piece in pieces:
            Gui.Selection.addSelection(piece)
        FittingCommands.add_selected_pattern_pieces()
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(fitting)
    if Gui.Control.activeDialog():
        Gui.Control.closeDialog()
    Gui.activateWorkbench("ClothSewingWorkbench")
    doc.recompute()
    return fitting


def reset_arrangement_from_simulation():
    """Reset the existing fitting scene to its saved home placements."""
    from freecad_cloth.avatar import FittingCommands

    return FittingCommands.reset_arrangement()
