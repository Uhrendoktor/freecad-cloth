"""Native UI handoff from Simulation to the existing Cloth fitting stage.

This module bridges already-authored simulation inputs into the persistent
FittingScene. It does not introduce placement heuristics or solver state.
"""


def _fitting_scene(doc):
    return next(
        (obj for obj in getattr(doc, "Objects", ()) if getattr(obj, "FittingType", "") == "FittingScene"),
        None,
    )


def fitting_stage_status(simulation):
    """Return a user-facing fitting status plus whether reset is available."""
    if simulation is None:
        return "No simulation scene selected.", False
    doc = getattr(simulation, "Document", None)
    fitting = _fitting_scene(doc) if doc is not None else None
    if fitting is None:
        return "Not arranged yet — use Arrange / Fit… to open the fitting stage.", False
    count = len(tuple(getattr(fitting, "PatternPieces", ()) or ()))
    state = str(getattr(fitting, "FitStatus", "Unassigned"))
    noun = "piece" if count == 1 else "pieces"
    return "%s | %d %s assigned" % (state, count, noun), count > 0


def open_arrange_fit_from_simulation(simulation):
    """Hand current simulation pieces/target to the persistent fitting scene."""
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

    target = getattr(simulation, "DrapeTarget", None)
    source = getattr(target, "SourceObject", None) if target is not None else None
    if source is not None:
        try:
            FittingCommands.assign_avatar_source(source)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            # Keep the authoritative simulation target untouched when the fitting
            # scene cannot represent the source as an AvatarProxy.
            pass

    fitting = FittingCommands.create_fitting_scene()
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(fitting)
    if Gui.Control.activeDialog():
        Gui.Control.closeDialog()
    Gui.activateWorkbench("Cloth Sewing")
    doc.recompute()
    return fitting


def reset_arrangement_from_simulation():
    """Reset the existing fitting scene to its saved home placements."""
    from freecad_cloth.avatar import FittingCommands

    return FittingCommands.reset_arrangement()
