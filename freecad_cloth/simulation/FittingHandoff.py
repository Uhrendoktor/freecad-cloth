"""Native UI handoff from Simulation to the existing Cloth fitting stage.

The persistent FittingScene remains the fitting-stage authority. This bridge
copies only the already-authored garment pieces from Simulation and opens the
existing fitting task. The Simulation-owned DrapeTarget remains authoritative;
it is mirrored only when an existing persisted FittingScene.DrapeTarget property
is already present.
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
    target = getattr(simulation, "DrapeTarget", None)
    target_info = {"state": "missing", "message": "No drape target selected"}
    try:
        from freecad_cloth.simulation.DrapeTarget import target_status
        target_info = target_status(target)
    except (ImportError, AttributeError, TypeError, ValueError):
        pass
    status_target = target
    if fitting is not None and "DrapeTarget" in getattr(fitting, "PropertiesList", ()):
        status_target = getattr(fitting, "DrapeTarget", None) or target
        try:
            from freecad_cloth.simulation.DrapeTarget import target_status
            target_info = target_status(status_target)
        except (ImportError, AttributeError, TypeError, ValueError):
            pass
    target_state = str(target_info.get("state", "blocked"))
    if target_state not in {"ready", "stale"}:
        target_state = "blocked"
    if fitting is None:
        return (
            "Arrange / Fit: not started | 0 pieces assigned | target: %s — %s"
            % (target_state, target_info["message"]),
            False,
        )
    pieces = len(tuple(getattr(fitting, "PatternPieces", ()) or ()))
    placements = len(tuple(getattr(fitting, "PiecePlacements", ()) or ()))
    points = len(tuple(getattr(fitting, "ArrangementPoints", ()) or ()))
    state = str(getattr(fitting, "FitStatus", "Unassigned"))
    noun = "piece" if pieces == 1 else "pieces"
    message = (
        "Arrange / Fit: %s | %d %s assigned | %d/%d saved placement(s) | "
        "%d arrangement point(s) | target: %s — %s"
    ) % (state, pieces, noun, placements, pieces, points, target_state, target_info["message"])
    return message, bool(tuple(getattr(fitting, "HomePlacements", ()) or ()))


def open_arrange_fit_from_simulation(simulation):
    """Open the existing fitting stage for the simulation's pieces and target."""
    import FreeCAD as App
    import FreeCADGui as Gui
    doc = getattr(simulation, "Document", None) or App.ActiveDocument
    if doc is None:
        raise RuntimeError("open a document before opening Arrange / Fit")
    from freecad_cloth.avatar import FittingCommands
    fitting = FittingCommands.create_fitting_scene()
    target = getattr(simulation, "DrapeTarget", None)
    pieces = tuple(getattr(simulation, "ClothPieces", ()) or ())
    if pieces:
        Gui.Selection.clearSelection()
        for piece in pieces:
            Gui.Selection.addSelection(piece)
        FittingCommands.add_selected_pattern_pieces()
    if target is not None and "DrapeTarget" in getattr(fitting, "PropertiesList", ()):
        fitting.DrapeTarget = target
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
