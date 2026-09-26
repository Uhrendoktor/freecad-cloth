"""Native UI handoff from Simulation to the existing Cloth fitting stage.

The persistent FittingScene remains the fitting-stage authority. This bridge
copies only the already-authored garment pieces from Simulation and preserves
the existing HomePlacements/Reset arrangement semantics. The simulation
DrapeTarget remains its own authoritative target.
"""


def _fitting_scene(doc):
    return next(
        (obj for obj in getattr(doc, "Objects", ()) if getattr(obj, "FittingType", "") == "FittingScene"),
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
        state, pieces, noun, placements, pieces, points,
    )
    can_reset = bool(tuple(getattr(fitting, "HomePlacements", ()) or ()))
    return message, can_reset


def open_arrange_fit_from_simulation(simulation):
    """Hand current simulation cloth pieces to the existing fitting stage."""
    import FreeCAD as App
    import FreeCADGui as Gui

    doc = getattr(simulation, "Document", None) or App.ActiveDocument
    if doc is None:
        raise RuntimeError("open a document before opening Arrange / Fit")

    from freecad_cloth.avatar import FittingCommands

    fitting = FittingCommands.create_fitting_scene()
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
