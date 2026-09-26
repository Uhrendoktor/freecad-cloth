"""Native UI handoff from Simulation to the existing Cloth fitting stage.

The persistent FittingScene remains the fitting-stage authority. This bridge
copies only the already-authored garment pieces from Simulation and carries the
same persistent DrapeTarget into fitting, preserving HomePlacements/Reset.
"""


def _fitting_scene(doc):
    return next(
        (obj for obj in getattr(doc, "Objects", ()) if getattr(obj, "FittingType", "") == "FittingScene"),
        None,
    )


def fitting_stage_status(simulation):
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
    return (
        "%s | %d %s assigned | %d/%d saved placement(s) | %d arrangement point(s)"
        % (state, pieces, noun, placements, pieces, points)
    ), bool(tuple(getattr(fitting, "HomePlacements", ()) or ()))


def open_arrange_fit_from_simulation(simulation):
    import FreeCAD as App
    import FreeCADGui as Gui
    doc = getattr(simulation, "Document", None) or App.ActiveDocument
    if doc is None:
        raise RuntimeError("open a document before opening Arrange / Fit")
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
    from freecad_cloth.avatar import FittingCommands
    return FittingCommands.reset_arrangement()
