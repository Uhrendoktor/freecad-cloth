# Copyright (C) 2026 FreeCAD Cloth contributors
"""Canonical FreeCAD/Xvfb acceptance for simulation quality/material controls."""

import contextlib
import os
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

import FreeCAD as App
import FreeCADGui as Gui
import Part
try:
    from PySide import QtWidgets
except ImportError:
    from PySide2 import QtWidgets


def _progress(message: str) -> None:
    """Persist milestones so CI timeouts show where native FreeCAD stopped.

    Args:
        message: One progress marker to append to the simulation log.
    """
    directory = Path(os.environ.get("CLOTH_SIMULATION_QUALITY_ARTIFACT_DIR", "artifacts"))
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "simulation-quality-progress.log"
    with path.open("a", encoding="utf-8") as stream:
        stream.write(message + "\n")
        stream.flush()


_progress("fixture-imported")


def _events() -> None:
    """Process pending FreeCAD and Qt events before inspecting GUI state."""
    Gui.updateGui()
    QtWidgets.QApplication.processEvents()


def _capture_readiness_screen(path: str) -> dict[str, int]:
    """Capture and validate the visible Simulation Quality task panel.

    Args:
        path: Destination path for the 1280-by-720 PNG screenshot.

    Returns:
        Pixel metrics reported by the shared visual-capture contract validator.

    Raises:
        RuntimeError: If FreeCAD's window or screen is unavailable, the capture has
            invalid dimensions, the screenshot is empty, or saving fails.
    """
    app = QtWidgets.QApplication.instance()
    screen = None if app is None else app.primaryScreen()
    window = Gui.getMainWindow()
    if app is None or screen is None or window is None:
        raise RuntimeError("FreeCAD main window/screen is unavailable for readiness screenshot")

    geometry = screen.availableGeometry()
    if geometry.width() < 1280 or geometry.height() < 720:
        raise RuntimeError(
            f"Simulation readiness screenshot requires a 1280x720-capable screen, got {geometry.width()}x{geometry.height()}"
        )

    window.resize(1280, 720)
    window.show()
    if hasattr(window, "raise_"):
        window.raise_()
    if hasattr(window, "activateWindow"):
        window.activateWindow()
    _events()
    time.sleep(0.10)
    _events()

    pixmap = screen.grabWindow(int(window.winId()))
    if pixmap.isNull():
        raise RuntimeError("FreeCAD readiness screenshot is null")
    width, height = int(pixmap.width()), int(pixmap.height())
    if (width, height) != (1280, 720):
        raise RuntimeError(
            f"Simulation readiness screenshot dimensions are {width}x{height}, expected 1280x720"
        )
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    if not pixmap.save(path):
        raise RuntimeError("failed to save Simulation Quality readiness screenshot")

    from freecad_cloth.common.VisualCaptureValidation import validate_png_capture

    return validate_png_capture(
        path,
        expected_width=1280,
        expected_height=720,
        min_nonwhite_pixels=500,
        min_distinct_rgb=16,
        min_opaque_pixels=500,
    )


def _close_task() -> None:
    """Close an active FreeCAD task dialog and process its close events."""
    if Gui.Control.activeDialog():
        Gui.Control.closeDialog()
        _events()


def _activate(name: str, commands: Sequence[str]) -> None:
    """Activate a workbench and verify its required command registrations.

    Args:
        name: Registered FreeCAD workbench name to activate.
        commands: Command identifiers that must be available afterward.

    Raises:
        RuntimeError: If the workbench cannot be activated or a command is missing.
    """
    Gui.activateWorkbench(name)
    _events()
    if Gui.activeWorkbench().name() != name:
        msg = f"failed to activate {name}"
        raise RuntimeError(msg)
    missing = [command for command in commands if command not in Gui.listCommands()]
    if missing:
        raise RuntimeError("commands are not registered: {}".format(",".join(missing)))


class _PlacementBase(Protocol):
    """Expose the X coordinate read by the acceptance fixture."""

    x: float


class _PatternPlacement(Protocol):
    """Expose the placement base used by a pattern piece."""

    Base: _PlacementBase


class _PatternPieceObject(Protocol):
    """Describe the pattern-piece properties used by acceptance setup."""

    PatternType: str
    Placement: _PatternPlacement


class _DocumentObjects(Protocol):
    """Expose the native document object's pattern inventory."""

    Objects: Sequence[_PatternPieceObject]


def _find_pieces(doc: _DocumentObjects) -> list[_PatternPieceObject]:
    """Return the native document's pattern-piece objects.

    Args:
        doc: FreeCAD document exposing its object inventory.

    Returns:
        Objects marked with the persistent PatternPiece type identifier.
    """
    return [
        obj for obj in doc.Objects if getattr(obj, "PatternType", "") == "PatternPiece"
    ]


def _panel_value(panel: object, widget_name: str) -> float:
    """Read a numeric value from a named Simulation Quality control.

    Args:
        panel: Task-panel instance containing the named widget.
        widget_name: Attribute name of the numeric widget.

    Returns:
        Current widget value converted to a floating-point number.
    """
    return float(getattr(panel, widget_name).value())


def run_acceptance() -> None:
    """Exercise public workbench commands, persistence and quality readiness.

    Raises:
        RuntimeError: If any asserted workbench, target, material, persistence or
            visual-readiness condition does not hold.
    """
    _progress("acceptance-start")
    doc = App.newDocument("SimulationQualityAcceptance")
    _progress("document-created")
    try:
        _activate("ClothPatternWorkbench", ["ClothPattern_CreatePieceWithSketch"])
        _progress("pattern-workbench-activated")
        Gui.runCommand("ClothPattern_CreatePieceWithSketch", 0)
        _progress("front-piece-command-finished")
        Gui.runCommand("ClothPattern_CreatePieceWithSketch", 0)
        _progress("back-piece-command-finished")
        pieces = _find_pieces(doc)
        if len(pieces) != 2:
            msg = "public Pattern command did not create two PatternPiece objects"
            raise RuntimeError(msg)
        front, back = pieces
        front.Placement.Base.x = -140
        back.Placement.Base.x = 20
        doc.recompute()
        _progress("pattern-pieces-created")

        _activate(
            "ClothSimulationWorkbench",
            ["ClothSimulation_Create", "ClothSimulation_Edit", "ClothSimulation_Reset"],
        )
        Gui.Selection.clearSelection()
        _progress("simulation-workbench-activated")
        Gui.runCommand("ClothSimulation_Create", 0)
        _progress("simulation-create-command-finished")
        scene = doc.getObject("ClothSimulation")
        if scene is None:
            msg = "public Simulation Create command did not create a ClothSimulation object"
            raise RuntimeError(msg)
        scene.ClothPieces = [front, back]

        target_body = doc.addObject("Part::Feature", "QualityAcceptanceTarget")
        target_body.Label = "Quality Acceptance Target"
        target_body.Shape = Part.makeCylinder(35, 100, App.Vector(-10, 0, -50))
        doc.recompute()
        _activate(
            "ClothSimulationWorkbench",
            [
                "ClothDrape_CreateTarget",
                "ClothDrape_RefreshTarget",
                "ClothSimulation_Edit",
                "ClothSimulation_Step",
            ],
        )
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(target_body)
        Gui.runCommand("ClothDrape_CreateTarget", 0)
        _progress("drape-target-command-finished")
        doc.recompute()
        target = doc.getObject("DrapeTarget")
        if target is None or scene.DrapeTarget != target:
            msg = "public DrapeTarget command did not attach the target to the simulation"
            raise RuntimeError(msg)
        Gui.runCommand("ClothDrape_RefreshTarget", 0)
        doc.recompute()

        from freecad_cloth.simulation.DrapeTarget import target_status
        from freecad_cloth.simulation.SimulationQuality import preset
        from freecad_cloth.simulation.SimulationQualityGui import SimulationQualityTaskPanel
        from freecad_cloth.simulation.SimulationQualityRuntime import (
            apply_quality_preset,
            ensure_quality_properties,
        )

        ensure_quality_properties(scene)
        apply_quality_preset(scene, "Fast")
        doc.recompute()
        fast = {
            "particle": float(scene.ParticleDistance),
            "iterations": int(scene.SolverIterations),
            "substeps": int(scene.SolverSubsteps),
            "density": float(scene.FabricDensity),
            "thickness": float(scene.FabricThickness),
            "particles": int(scene.ParticleCount),
        }
        final = preset("Final")
        if fast["particle"] <= final.particle_distance:
            msg = "Fast preset did not use a coarser particle distance than Final"
            raise RuntimeError(msg)
        if fast["iterations"] >= final.solver_iterations:
            msg = "Fast preset did not use fewer solver iterations than Final"
            raise RuntimeError(msg)
        if fast["particles"] <= 0:
            msg = "Fast preset did not build a real simulation discretization"
            raise RuntimeError(msg)

        panel = SimulationQualityTaskPanel(scene)
        Gui.Control.showDialog(panel)
        _events()
        _progress("ready-panel-shown")
        if not hasattr(panel, "arrange_fit_button") or not hasattr(panel, "snap_to_target_button"):
            msg = "simulation panel did not expose the Arrange / Fit / target-snap bridge"
            raise RuntimeError(msg)
        if not hasattr(panel, "workflow_labels") or set(panel.workflow_labels) != {
            "patterns",
            "sewing",
            "target",
            "arrangement",
            "simulation",
        }:
            raise RuntimeError(
                "simulation panel did not expose the complete workflow readiness checklist"
            )
        if panel.workflow_labels["patterns"].property("workflowState") != "ready":
            raise RuntimeError("workflow checklist did not recognize the assigned pattern pieces")
        if panel.workflow_labels["target"].property("workflowState") != "ready":
            raise RuntimeError("workflow checklist did not recognize the current drape target")
        if panel.workflow_labels["simulation"].property("workflowState") != "ready":
            raise RuntimeError("workflow checklist did not recognize the minimum simulation inputs")
        artifact_dir = os.environ.get("CLOTH_SIMULATION_QUALITY_ARTIFACT_DIR", "artifacts")
        readiness_image = os.path.join(artifact_dir, "simulation-quality-readiness.png")
        readiness_metrics = _capture_readiness_screen(readiness_image)
        print(
            "simulation-quality-readiness-screenshot=passed path=%s metrics=%s"
            % (readiness_image, readiness_metrics),
            flush=True,
        )
        if panel.reset_arrangement_button.isEnabled():
            msg = "reset arrangement should be disabled before fitting handoff"
            raise RuntimeError(msg)
        _progress("ready-screenshot-saved")
        panel.quality.setCurrentText("Final")
        _events()
        doc.recompute()
        if str(scene.QualityPreset) != "Final":
            msg = "task panel did not persist the selected quality preset"
            raise RuntimeError(msg)
        if abs(float(scene.ParticleDistance) - float(final.particle_distance)) > 1e-6:
            msg = "Final preset did not persist its particle distance"
            raise RuntimeError(msg)
        if int(scene.SolverIterations) != int(final.solver_iterations):
            msg = "Final preset did not persist its solver iterations"
            raise RuntimeError(msg)
        if int(scene.SolverSubsteps) != int(final.substeps):
            msg = "Final preset did not persist its solver substeps"
            raise RuntimeError(msg)
        if int(scene.ParticleCount) <= fast["particles"]:
            msg = "Final preset did not materially increase simulation discretization"
            raise RuntimeError(msg)
        panel.density.setValue(225.0)
        panel.thickness.setValue(0.75)
        panel.skin_offset.setValue(2.5)
        panel.friction.setValue(0.65)
        panel.accept()
        _close_task()
        doc.recompute()
        authored = (
            str(scene.QualityPreset),
            float(scene.FabricDensity),
            float(scene.FabricThickness),
            float(scene.AvatarSkinOffset),
            float(scene.FabricFriction),
        )
        if authored != ("Final", 225.0, 0.75, 2.5, 0.65):
            msg = "task-panel material/collision edits did not persist into document properties"
            raise RuntimeError(msg)

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "simulation-quality-acceptance.FCStd")
            doc.saveAs(path)
            App.closeDocument(doc.Name)
            doc = None
            reloaded = App.openDocument(path)
            _progress("document-reloaded")
            scene = reloaded.getObject("ClothSimulation")
            target = reloaded.getObject("DrapeTarget")
            target_body = reloaded.getObject("QualityAcceptanceTarget")
            if scene is None or target is None or target_body is None:
                msg = "quality simulation did not survive save/reload"
                raise RuntimeError(msg)
            persisted = (
                str(scene.QualityPreset),
                float(scene.FabricDensity),
                float(scene.FabricThickness),
                float(scene.AvatarSkinOffset),
                float(scene.FabricFriction),
                float(scene.ParticleDistance),
                int(scene.SolverIterations),
                int(scene.SolverSubsteps),
            )
            expected = (
                "Final",
                225.0,
                0.75,
                2.5,
                0.65,
                float(final.particle_distance),
                int(final.solver_iterations),
                int(final.substeps),
            )
            if persisted != expected:
                msg = "quality, material, and collision controls did not persist across save/reload"
                raise RuntimeError(msg)
            _activate(
                "ClothSimulationWorkbench",
                [
                    "ClothSimulation_Edit",
                    "ClothSimulation_Reset",
                    "ClothSimulation_Step",
                    "ClothDrape_RefreshTarget",
                ],
            )
            panel = SimulationQualityTaskPanel(scene)
            Gui.Control.showDialog(panel)
            _events()
            if panel.quality.currentText() != "Final":
                msg = "reloaded task panel lost the authored quality preset"
                raise RuntimeError(msg)
            if (
                abs(_panel_value(panel, "density") - 225.0) > 1e-6
                or abs(_panel_value(panel, "thickness") - 0.75) > 1e-6
            ):
                msg = "reloaded task panel lost authored fabric controls"
                raise RuntimeError(msg)
            if abs(_panel_value(panel, "skin_offset") - 2.5) > 1e-6:
                msg = "reloaded task panel lost authored collision control"
                raise RuntimeError(msg)
            _close_task()

            target_body.Placement.Base.x += 15.0
            reloaded.recompute()
            _progress("target-made-stale")
            status = target_status(target)
            if status["state"] != "stale" or not status["stale"]:
                msg = "upstream CAD target edit did not produce deterministic stale state"
                raise RuntimeError(msg)
            panel = SimulationQualityTaskPanel(scene)
            Gui.Control.showDialog(panel)
            _events()
            if (
                panel.step_button.isEnabled()
                or panel.run_button.isEnabled()
                or not panel.reset_button.isEnabled()
            ):
                msg = "stale-target status did not block Step/Run while preserving Reset"
                raise RuntimeError(msg)
            if "Simulation blocked" not in panel.status.text():
                msg = "stale-target status did not expose a user-facing blocked reason"
                raise RuntimeError(msg)
            if panel.workflow_labels["target"].property("workflowState") != "blocked":
                raise RuntimeError("workflow checklist did not mark a stale drape target blocked")
            if panel.workflow_labels["simulation"].property("workflowState") != "blocked":
                raise RuntimeError("workflow checklist did not block simulation for a stale target")
            _progress("stale-panel-shown")
            stale_image = os.path.join(artifact_dir, "simulation-quality-stale-target.png")
            stale_metrics = _capture_readiness_screen(stale_image)
            print(
                "simulation-quality-stale-target-screenshot=passed path=%s metrics=%s"
                % (stale_image, stale_metrics),
                flush=True,
            )
            _progress("stale-screenshot-saved")
            _close_task()

            Gui.Selection.clearSelection()
            Gui.Selection.addSelection(scene)
            Gui.runCommand("ClothSimulation_Reset", 0)
            Gui.runCommand("ClothDrape_RefreshTarget", 0)
            reloaded.recompute()
            status = target_status(target)
            if status["state"] != "ready":
                msg = "public DrapeTarget refresh did not restore a ready target"
                raise RuntimeError(msg)
            _progress("target-refresh-finished")
            Gui.runCommand("ClothSimulation_Step", 0)
            reloaded.recompute()
            _progress("simulation-step-finished")
            if int(scene.Steps) != 1 or not bool(scene.FiniteState):
                msg = "public Simulation Step did not recover after stale-target refresh"
                raise RuntimeError(msg)
            App.closeDocument(reloaded.Name)
            doc = None
        print("simulation quality persistence acceptance passed", flush=True)
    finally:
        _close_task()
        if doc is not None:
            with contextlib.suppress(Exception):
                App.closeDocument(doc.Name)


_progress("entrypoint-entered")
try:
    run_acceptance()
except BaseException as exc:
    print("simulation-quality-acceptance=failed error=%r" % (exc,), flush=True)
    App.Console.PrintError("Simulation Quality acceptance failed: %s\\n" % exc)
    os._exit(1)
os._exit(0)
