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


def _target_display_state(info):
    """Map the canonical DrapeTarget contract to concise UI states."""
    state = str(info.get("state", "invalid"))
    if state == "ready":
        return "ready"
    if state == "stale":
        return "stale"
    return "blocked"


def fitting_stage_status(simulation):
    """Return visible fitting/target state plus whether Reset arrangement is available."""
    if simulation is None:
        return "No simulation scene selected.", False

    target = getattr(simulation, "DrapeTarget", None)
    target_info = {
        "state": "missing",
        "message": "No drape target selected",
        "stale": True,
        "reason": "target missing",
    }
    try:
        from freecad_cloth.simulation.DrapeTarget import target_status
        target_info = target_status(target)
    except (ImportError, AttributeError, TypeError, ValueError):
        pass

    doc = getattr(simulation, "Document", None)
    fitting = _fitting_scene(doc) if doc is not None else None
    target_state = _target_display_state(target_info)

    if fitting is None:
        return (
            "Arrange / Fit: not started | 0 pieces assigned | target: %s — %s"
            % (target_state, target_info["message"]),
            False,
        )

    fitting_target = getattr(fitting, "DrapeTarget", None)
    if fitting_target is not None:
        try:
            from freecad_cloth.simulation.DrapeTarget import target_status
            target_info = target_status(fitting_target)
            target_state = _target_display_state(target_info)
        except (ImportError, AttributeError, TypeError, ValueError):
            pass

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
    if target is not None:
        fitting.DrapeTarget = target
    pieces = tuple(getattr(simulation, "ClothPieces", ()) or ())
    if pieces:
        Gui.Selection.clearSelection()
        for piece in pieces:
            Gui.Selection.addSelection(piece)
        FittingCommands.add_selected_pattern_pieces()
        # Re-assert the exact Simulation-owned target after the fitting scene
        # mutates its persisted piece/placement collections.
        if target is not None:
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
