"""Single-owner bridge from Simulation Quality UI to the persistent fitting workflow."""

def _fit_scene_for_simulation(simulation_scene):
    import FreeCAD as App
    from freecad_cloth.avatar.FittingCommands import create_fitting_scene
    document = getattr(simulation_scene, "Document", None) or App.ActiveDocument
    if document is None:
        raise ValueError("open a document before arranging garment pieces")
    fitting = create_fitting_scene()
    target = getattr(simulation_scene, "DrapeTarget", None)
    if target is not None:
        fitting.DrapeTarget = target
    avatar = getattr(simulation_scene, "AvatarProxy", None)
    if avatar is not None:
        fitting.AvatarProxy = avatar
    pieces = list(getattr(simulation_scene, "ClothPieces", ()) or ())
    if not pieces:
        raise ValueError("no garment pieces are assigned to the simulation")
    fitting.PatternPieces = pieces

    from freecad_cloth.avatar.AvatarFitting import PiecePlacement
    if not getattr(fitting, "PiecePlacements", None):
        records = []
        for piece in pieces:
            base = piece.Placement.Base
            rotation = piece.Placement.Rotation
            axis = getattr(rotation, "Axis", None)
            axis_values = (
                (float(axis.x), float(axis.y), float(axis.z))
                if axis is not None else (0.0, 0.0, 1.0)
            )
            try:
                records.append(
                    PiecePlacement(
                        str(piece.PieceId),
                        (float(base.x), float(base.y), float(base.z)),
                        float(rotation.Angle),
                        axis_values,
                    ).to_string()
                )
            except TypeError:
                records.append(
                    PiecePlacement(
                        str(piece.PieceId),
                        (float(base.x), float(base.y), float(base.z)),
                        float(rotation.Angle),
                    ).to_string()
                )
        fitting.PiecePlacements = list(records)
    if not getattr(fitting, "HomePlacements", None):
        fitting.HomePlacements = list(fitting.PiecePlacements)
    if str(getattr(fitting, "FitStatus", "")) in {"", "Unassigned"}:
        fitting.FitStatus = "Ready"
    return fitting


def fitting_summary(simulation_scene):
    """Return UI-safe fitting state without implementing placement."""
    from freecad_cloth.simulation.DrapeTarget import target_status
    try:
        fitting = _fit_scene_for_simulation(simulation_scene)
    except ValueError as exc:
        return {
            "fitting": None,
            "target_state": "missing",
            "target_message": str(exc),
            "pieces": 0,
            "arrangement_points": 0,
            "fit_status": "Unavailable",
        }
    target = getattr(fitting, "DrapeTarget", None)
    target_info = target_status(target)
    return {
        "fitting": fitting,
        "target_state": target_info["state"],
        "target_message": target_info["message"],
        "pieces": len(getattr(fitting, "PatternPieces", ()) or ()),
        "arrangement_points": len(getattr(fitting, "ArrangementPoints", ()) or ()),
        "fit_status": str(getattr(fitting, "FitStatus", "Unassigned")),
    }


def arrange_and_fit(simulation_scene):
    """Delegate placement to FittingCommands, then invalidate solver state."""
    from freecad_cloth.avatar.FittingCommands import snap_pattern_pieces_to_target
    from freecad_cloth.simulation.SimulationObjects import reset_scene

    fitting = _fit_scene_for_simulation(simulation_scene)
    target = getattr(fitting, "DrapeTarget", None)
    if target is None:
        raise ValueError("assign a DrapeTarget before using Arrange / Fit")
    result = snap_pattern_pieces_to_target(
        pieces=list(fitting.PatternPieces),
        target=target,
    )
    simulation_scene.DrapeTarget = target
    simulation_scene.ClothPieces = list(fitting.PatternPieces)
    reset_scene(simulation_scene)
    simulation_scene.Document.recompute()
    return result


def reset_arrangement(simulation_scene):
    """Delegate reset to FittingCommands, then invalidate solver state."""
    from freecad_cloth.avatar.FittingCommands import reset_arrangement
    from freecad_cloth.simulation.SimulationObjects import reset_scene

    fitting = _fit_scene_for_simulation(simulation_scene)
    result = reset_arrangement()
    simulation_scene.DrapeTarget = getattr(fitting, "DrapeTarget", None)
    simulation_scene.ClothPieces = list(fitting.PatternPieces)
    reset_scene(simulation_scene)
    simulation_scene.Document.recompute()
    return result
