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

        panel = SimulationQualityTaskPanel(scene)
        Gui.Control.showDialog(panel)
        _events()
        panel._preset_changed("Final")
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
            doc.saveAs(path)
            App.closeDocument(doc.Name)
            doc = None
            reloaded = App.openDocument(path)
            scene = reloaded.getObject("ClothSimulation")
            target = reloaded.getObject("DrapeTarget")
            target_body = reloaded.getObject("QualityAcceptanceTarget")
            if scene is None or target is None or target_body is None:
                raise RuntimeError("quality simulation did not survive save/reload")
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
