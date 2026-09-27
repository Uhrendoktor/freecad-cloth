"""Canonical FreeCAD/Xvfb acceptance for simulation quality/material controls."""
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
import Part


def _events():
    Gui.updateGui()
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    QtWidgets.QApplication.processEvents()


def _close_task():
    if Gui.Control.activeDialog():
        Gui.Control.closeDialog()
        _events()


def _activate(name, commands):
    Gui.activateWorkbench(name)
    _events()
    if Gui.activeWorkbench().name() != name:
        raise RuntimeError("failed to activate %s" % name)
    missing = [command for command in commands if command not in Gui.listCommands()]
    if missing:
        raise RuntimeError("commands are not registered: %s" % ",".join(missing))


def _find_pieces(doc):
    return [obj for obj in doc.Objects if getattr(obj, "PatternType", "") == "PatternPiece"]


def _panel_value(panel, widget_name):
    return getattr(panel, widget_name).value()


def _placement_signature(piece):
    placement = piece.Placement
    base = placement.Base
    axis = placement.Rotation.Axis
    return (
        float(base.x), float(base.y), float(base.z),
        float(axis.x), float(axis.y), float(axis.z), float(placement.Rotation.Angle),
    )


def _sketch_placement_signature(piece):
    sketch = getattr(piece, "Sketch", None)
    return None if sketch is None else _placement_signature(sketch)


def _piece_world_vertices(piece):
    return tuple(
        tuple(float(value) for value in (piece.Placement.multVec(vertex.Point).x,
                                         piece.Placement.multVec(vertex.Point).y,
                                         piece.Placement.multVec(vertex.Point).z))
        for vertex in getattr(piece.Shape, "Vertexes", ())
    )


def run_acceptance():
    doc = App.newDocument("SimulationQualityAcceptance")
    try:
        _activate("ClothPatternWorkbench", ["ClothPattern_CreatePieceWithSketch"])
        Gui.runCommand("ClothPattern_CreatePieceWithSketch", 0)
        Gui.runCommand("ClothPattern_CreatePieceWithSketch", 0)
        pieces = _find_pieces(doc)
        if len(pieces) != 2:
            raise RuntimeError("public Pattern command did not create two PatternPiece objects")
        front, back = pieces
        front.Placement.Base.x = -140
        back.Placement.Base.x = 20
        doc.recompute()

        _activate("ClothSimulationWorkbench", ["ClothSimulation_Create", "ClothSimulation_Edit", "ClothSimulation_Reset"])
        Gui.Selection.clearSelection()
        Gui.runCommand("ClothSimulation_Create", 0)
        scene = doc.getObject("ClothSimulation")
        if scene is None:
            raise RuntimeError("public Simulation Create command did not create a ClothSimulation object")
        scene.ClothPieces = [front, back]

        target_body = doc.addObject("Part::Feature", "QualityAcceptanceTarget")
        target_body.Label = "Quality Acceptance Target"
        target_body.Shape = Part.makeCylinder(35, 100, App.Vector(-10, 0, -50))
        # Exercise the production world-space target transform rather than an
        # identity-placement-only fixture; target geometry may be placed in the
        # FreeCAD document independently from its local tessellation.
        target_body.Placement.Base = App.Vector(17.0, 12.0, 25.0)
        doc.recompute()
        _activate("ClothSimulationWorkbench", ["ClothDrape_CreateTarget", "ClothDrape_RefreshTarget", "ClothSimulation_Edit", "ClothSimulation_Step"])
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(target_body)
        Gui.runCommand("ClothDrape_CreateTarget", 0)
        doc.recompute()
        target = doc.getObject("DrapeTarget")
        if target is None or scene.DrapeTarget != target:
            raise RuntimeError("public DrapeTarget command did not attach the target to the simulation")
        Gui.runCommand("ClothDrape_RefreshTarget", 0)
        doc.recompute()

        from freecad_cloth.simulation.SimulationQualityRuntimeV2 import apply_quality_preset, ensure_quality_properties
        from freecad_cloth.simulation.SimulationQuality import preset
        from freecad_cloth.simulation.SimulationQualityGui import SimulationQualityTaskPanel
        from freecad_cloth.simulation.DrapeTarget import target_status

        ensure_quality_properties(scene)
        apply_quality_preset(scene, "Fast")
        doc.recompute()
        fast = {"particle": float(scene.ParticleDistance), "iterations": int(scene.SolverIterations), "substeps": int(scene.SolverSubsteps), "density": float(scene.FabricDensity), "thickness": float(scene.FabricThickness), "particles": int(scene.ParticleCount)}
        final = preset("Final")
        if fast["particle"] <= final.particle_distance:
            raise RuntimeError("Fast preset did not use a coarser particle distance than Final")
        if fast["iterations"] >= final.solver_iterations:
            raise RuntimeError("Fast preset did not use fewer solver iterations than Final")
        if fast["particles"] <= 0:
            raise RuntimeError("Fast preset did not build a real simulation discretization")

        panel = SimulationQualityTaskPanel(scene)
        Gui.Control.showDialog(panel)
        _events()
        if not hasattr(panel, "arrange_fit_button") or not hasattr(panel, "snap_to_target_button"):
            raise RuntimeError("simulation panel did not expose the Arrange / Fit / target-snap bridge")
        if panel.reset_arrangement_button.isEnabled():
            raise RuntimeError("reset arrangement should be disabled before fitting handoff")
        panel.quality.setCurrentText("Final")
        _events()
        doc.recompute()
        if str(scene.QualityPreset) != "Final":
            raise RuntimeError("task panel did not persist the selected quality preset")
        if abs(float(scene.ParticleDistance) - float(final.particle_distance)) > 1e-6:
            raise RuntimeError("Final preset did not persist its particle distance")
        if int(scene.SolverIterations) != int(final.solver_iterations):
            raise RuntimeError("Final preset did not persist its solver iterations")
        if int(scene.SolverSubsteps) != int(final.substeps):
            raise RuntimeError("Final preset did not persist its solver substeps")
        if int(scene.ParticleCount) <= fast["particles"]:
            raise RuntimeError("Final preset did not materially increase simulation discretization")
        panel.density.setValue(225.0)
        panel.thickness.setValue(0.75)
        panel.skin_offset.setValue(2.5)
        panel.friction.setValue(0.65)
        panel.accept()
        _close_task()
        doc.recompute()
        authored = (str(scene.QualityPreset), float(scene.FabricDensity), float(scene.FabricThickness), float(scene.AvatarSkinOffset), float(scene.FabricFriction))
        if authored != ("Final", 225.0, 0.75, 2.5, 0.65):
            raise RuntimeError("task-panel material/collision edits did not persist into document properties")

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "simulation-quality-acceptance.FCStd")
            front_piece_id = str(front.PieceId)
            back_piece_id = str(back.PieceId)
            doc.saveAs(path)
            App.closeDocument(doc.Name)
            doc = None
            reloaded = App.openDocument(path)
            scene = reloaded.getObject("ClothSimulation")
            reloaded_pieces = {str(piece.PieceId): piece for piece in _find_pieces(reloaded)}
            front = reloaded_pieces.get(front_piece_id)
            back = reloaded_pieces.get(back_piece_id)
            target = reloaded.getObject("DrapeTarget")
            target_body = reloaded.getObject("QualityAcceptanceTarget")
            if scene is None or target is None or target_body is None:
                raise RuntimeError("quality simulation did not survive save/reload")
            if front is None or back is None:
                raise RuntimeError("saved PatternPieces did not survive save/reload")
            persisted = (str(scene.QualityPreset), float(scene.FabricDensity), float(scene.FabricThickness), float(scene.AvatarSkinOffset), float(scene.FabricFriction), float(scene.ParticleDistance), int(scene.SolverIterations), int(scene.SolverSubsteps))
            expected = ("Final", 225.0, 0.75, 2.5, 0.65, float(final.particle_distance), int(final.solver_iterations), int(final.substeps))
            if persisted != expected:
                raise RuntimeError("quality, material, and collision controls did not persist across save/reload")
            _activate("ClothSimulationWorkbench", ["ClothSimulation_Edit", "ClothSimulation_Reset", "ClothSimulation_Step", "ClothDrape_RefreshTarget"])
            panel = SimulationQualityTaskPanel(scene)
            Gui.Control.showDialog(panel)
            _events()
            if panel.quality.currentText() != "Final":
                raise RuntimeError("reloaded task panel lost the authored quality preset")
            if abs(_panel_value(panel, "density") - 225.0) > 1e-6 or abs(_panel_value(panel, "thickness") - 0.75) > 1e-6:
                raise RuntimeError("reloaded task panel lost authored fabric controls")
            if abs(_panel_value(panel, "skin_offset") - 2.5) > 1e-6:
                raise RuntimeError("reloaded task panel lost authored collision control")
            snap_before = {str(piece.PieceId): _placement_signature(piece) for piece in (front, back)}
            snap_before_sketch = {str(piece.PieceId): _sketch_placement_signature(piece) for piece in (front, back)}

            panel = SimulationQualityTaskPanel(scene)
            Gui.Control.showDialog(panel)
            _events()
            if not hasattr(panel, "snap_to_target_button"):
                raise RuntimeError("simulation task panel lost the target-snap button")
            panel.snap_to_target_button.click()
            _events()
            reloaded.recompute()

            fitting = next((obj for obj in reloaded.Objects if getattr(obj, "FittingType", "") == "FittingScene"), None)
            if fitting is None:
                raise RuntimeError("Snap-to-target did not create or preserve the FittingScene")
            if getattr(fitting, "DrapeTarget", None) != target:
                raise RuntimeError("Snap-to-target did not preserve the persistent DrapeTarget identity")
            if str(getattr(fitting, "FitStatus", "")) != "Target-aware arrangement applied":
                raise RuntimeError("Snap-to-target did not expose the applied arrangement state")
            if not panel.reset_arrangement_button.isEnabled():
                raise RuntimeError("Snap-to-target did not expose a reversible Reset arrangement state")

            snap_after = {str(piece.PieceId): _placement_signature(piece) for piece in (front, back)}
            snap_after_sketch = {str(piece.PieceId): _sketch_placement_signature(piece) for piece in (front, back)}
            if snap_after == snap_before:
                raise RuntimeError("Snap-to-target did not move any PatternPiece")
            for piece_id in snap_before:
                if snap_after[piece_id][3:] != snap_before[piece_id][3:]:
                    raise RuntimeError("Snap-to-target changed a PatternPiece rotation")
                before_sketch = snap_before_sketch[piece_id]
                after_sketch = snap_after_sketch[piece_id]
                if before_sketch is not None and after_sketch is not None and after_sketch[3:] != before_sketch[3:]:
                    raise RuntimeError("Snap-to-target changed a native Sketch rotation")

            from freecad_cloth.avatar.TargetPlacement import nearest_surface_distance, point_inside_closed_surface
            from freecad_cloth.avatar.AvatarCollision import CollisionSurface
            from freecad_cloth.simulation.DrapeTarget import collision_surface
            local_surface = collision_surface(
                target.SourceObject,
                float(getattr(target, "CollisionDeflection", 1.0)),
                float(getattr(target, "CollisionThickness", 0.0)),
            )
            source_placement = getattr(target.SourceObject, "Placement", None)
            if source_placement is None:
                surface = local_surface
            else:
                world_vertices = []
                for x, y, z in local_surface.vertices:
                    point = source_placement.multVec(App.Vector(float(x), float(y), float(z)))
                    world_vertices.append((float(point.x), float(point.y), float(point.z)))
                surface = CollisionSurface(
                    tuple(world_vertices),
                    tuple(local_surface.triangles),
                    str(local_surface.region),
                    float(local_surface.thickness),
                )
                surface.validate()
            placed_points = tuple(
                point
                for piece in (front, back)
                for point in _piece_world_vertices(piece)
            )
            if not placed_points:
                raise RuntimeError("Snap-to-target produced no measurable PatternPiece vertices")
            if nearest_surface_distance(surface, placed_points) < 8.0 - 1e-6:
                raise RuntimeError("Snap-to-target failed its unchanged 8 mm collision-surface clearance gate")
            placed_centroid = tuple(
                sum(point[index] for point in placed_points) / float(len(placed_points))
                for index in range(3)
            )
            if point_inside_closed_surface(surface, placed_centroid):
                raise RuntimeError("Snap-to-target placed the garment centroid inside the closed DrapeTarget")
            print(
                "target-snap-ui-journey=passed target=%s clearance-mm=%.3f outside-centroid=true"
                % (target.Name, nearest_surface_distance(surface, placed_points)),
                flush=True,
            )

            panel.reset_arrangement_button.click()
            _events()
            reloaded.recompute()
            restored = {str(piece.PieceId): _placement_signature(piece) for piece in (front, back)}
            restored_sketch = {str(piece.PieceId): _sketch_placement_signature(piece) for piece in (front, back)}
            if restored != snap_before:
                raise RuntimeError("Reset arrangement did not restore exact PatternPiece placements")
            if restored_sketch != snap_before_sketch:
                raise RuntimeError("Reset arrangement did not restore exact native Sketch placements")
            if tuple(getattr(fitting, "PiecePlacements", ()) or ()) != tuple(getattr(fitting, "HomePlacements", ()) or ()):
                raise RuntimeError("Reset arrangement did not restore the fitting placement ledger")
            if panel.reset_arrangement_button.isEnabled():
                raise RuntimeError("Reset arrangement remained enabled after restoring HomePlacements")
            print("target-snap-reset=passed pattern-and-sketch-placements=true", flush=True)
            _close_task()

            _close_task()

            target_body.Placement.Base.x += 15.0
            reloaded.recompute()
            status = target_status(target)
            if status["state"] != "stale" or not status["stale"]:
                raise RuntimeError("upstream CAD target edit did not produce deterministic stale state")
            panel = SimulationQualityTaskPanel(scene)
            Gui.Control.showDialog(panel)
            _events()
            if panel.step_button.isEnabled() or panel.run_button.isEnabled() or not panel.reset_button.isEnabled():
                raise RuntimeError("stale-target status did not block Step/Run while preserving Reset")
            if "Simulation blocked" not in panel.status.text():
                raise RuntimeError("stale-target status did not expose a user-facing blocked reason")
            _close_task()

            Gui.Selection.clearSelection()
            Gui.Selection.addSelection(scene)
            Gui.runCommand("ClothSimulation_Reset", 0)
            Gui.runCommand("ClothDrape_RefreshTarget", 0)
            reloaded.recompute()
            status = target_status(target)
            if status["state"] != "ready":
                raise RuntimeError("public DrapeTarget refresh did not restore a ready target")
            Gui.runCommand("ClothSimulation_Step", 0)
            reloaded.recompute()
            if int(scene.Steps) != 1 or not bool(scene.FiniteState):
                raise RuntimeError("public Simulation Step did not recover after stale-target refresh")
            App.closeDocument(reloaded.Name)
            doc = None
        print("simulation quality persistence acceptance passed", flush=True)
    finally:
        _close_task()
        if doc is not None:
            try:
                App.closeDocument(doc.Name)
            except Exception:
                pass


if __name__ == "__main__":
    run_acceptance()
