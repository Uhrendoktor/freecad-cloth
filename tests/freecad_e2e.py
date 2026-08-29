"""Canonical native FreeCAD Pattern -> Sewing -> Simulation workflow scenario.

The scenario intentionally uses public workbench commands/task panels for seam
creation, sewing-operation creation, workbench activation, and simulation UI.
The document model helpers only construct deterministic fixture geometry.
"""
import os
import sys
import tempfile
import traceback
from pathlib import Path

import FreeCAD as App
import FreeCADGui as Gui

try:
    from PySide import QtWidgets
except ImportError:
    from PySide2 import QtWidgets

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
OUT = Path(os.environ.get("CLOTH_E2E_DIR", "artifacts/freecad-e2e"))
OUT.mkdir(parents=True, exist_ok=True)
LOG = OUT / "workflow.log"


def log(message):
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(message + "\n")
        handle.flush()


def process_events():
    QtWidgets.QApplication.processEvents()
    Gui.updateGui()
    QtWidgets.QApplication.processEvents()


def activate(name, toolbar, commands):
    if name not in Gui.listWorkbenches():
        raise AssertionError("workbench is not registered: %s" % name)
    Gui.activateWorkbench(name)
    process_events()
    active = Gui.activeWorkbench().name()
    if active != name:
        raise AssertionError("expected active workbench %s, got %s" % (name, active))
    window = Gui.getMainWindow()
    visible = [] if window is None else [bar.windowTitle() for bar in window.findChildren(QtWidgets.QToolBar) if bar.isVisible()]
    if toolbar not in visible:
        raise AssertionError("toolbar is not visible: %s" % toolbar)
    missing = [command for command in commands if command not in Gui.listCommands()]
    if missing:
        raise AssertionError("commands missing from %s: %s" % (name, ",".join(missing)))
    log("activated %s commands=%s" % (name, ",".join(commands)))


def show_panel(panel, label):
    Gui.Control.showDialog(panel)
    process_events()
    if not getattr(panel, "form", None) or not panel.form.isVisible():
        raise AssertionError("task panel did not become visible: %s" % label)
    log("task-panel visible=%s" % label)


def close_panel():
    try:
        Gui.Control.closeDialog()
    finally:
        process_events()


def make_piece(doc, name, points, piece_id):
    from PatternModel import PatternPiece
    from PatternObjects import add_pattern_piece

    piece = PatternPiece(name, list(points), id=piece_id, seam_allowance=10.0, grainline_angle=0.0)
    return add_pattern_piece(doc, piece)


def select_edges(*entries):
    Gui.Selection.clearSelection()
    for obj, edge in entries:
        Gui.Selection.addSelection(obj, "Edge%d" % (int(edge) + 1))
    process_events()


def run():
    from PatternGui import PatternDraftingTaskPanel
    from SewingGui import SewingTaskPanel
    from SimulationGui import SimulationTaskPanel

    doc = App.newDocument("CanonicalClothE2E")
    path = None
    try:
        log("scenario-start")
        # Two parametric pieces provide the save/reload + upstream invalidation path.
        front = make_piece(doc, "Front", [(0, 0), (140, 0), (140, 90), (0, 90)], "front")
        back = make_piece(doc, "Back", [(0, 0), (140, 0), (140, 90), (0, 90)], "back")
        back.Placement.Base.x = 170

        # Sleeve contours use deterministic sampled arc points. The M:N sewing
        # network joins three consecutive boundary segments, exercising the
        # curved-contour path without introducing a second source of geometry.
        import math
        curve = [(80 * math.cos(math.radians(a)), 80 * math.sin(math.radians(a))) for a in (0, 18, 36, 54, 72, 90)]
        sleeve_a = make_piece(doc, "SleeveA", [(0, 0)] + curve, "sleeve-a")
        sleeve_b = make_piece(doc, "SleeveB", [(0, 0)] + curve, "sleeve-b")
        sleeve_b.Placement.Base.x = 210
        doc.recompute()

        activate("ClothPatternWorkbench", "Cloth Pattern", [
            "ClothPattern_CreatePieceTask", "ClothPattern_EditPiece", "ClothPattern_Show2D", "ClothPattern_AddSeam"])
        show_panel(PatternDraftingTaskPanel(front), "Pattern Design")
        close_panel()

        # Use the public Pattern workbench command to create the canonical front/back seam.
        select_edges((front, 0), (back, 0))
        Gui.runCommand("ClothPattern_AddSeam", 0)
        process_events()
        seams = [obj for obj in doc.Objects if getattr(obj, "SeamId", "")]
        assert len(seams) == 1, "public Pattern seam command did not create exactly one seam"
        main_seam = seams[0]
        log("pattern-seam-created id=%s" % main_seam.SeamId)

        # Public Sewing workbench command creates the operation from the canonical seam.
        activate("ClothSewingWorkbench", "Cloth Sewing", [
            "ClothSewing_CreateSeam", "ClothSewing_CreateMNSewing", "ClothSewing_CreateOperation", "ClothSewing_EditOperation", "ClothSewing_Validate"])
        Gui.Selection.clearSelection(); Gui.Selection.addSelection(main_seam); process_events()
        Gui.runCommand("ClothSewing_CreateOperation", 0)
        process_events()
        operations = [obj for obj in doc.Objects if getattr(obj, "SewingType", "") == "SewingOperation"]
        assert len(operations) == 1, "public Sewing operation command did not create one operation"
        operation = operations[0]
        assert operation.Status == "Valid"
        log("sewing-operation-created status=%s length=%.3f" % (operation.Status, float(operation.LengthA)))

        # Exercise the actual Sewing task panel and its persistent controls.
        Gui.Selection.clearSelection(); Gui.Selection.addSelection(operation); process_events()
        panel = SewingTaskPanel(operation)
        show_panel(panel, "Sewing")
        panel.stitches.setValue(12)
        panel.alignment.setCurrentText("uniform")
        assert panel.accept() is True
        close_panel()
        doc.recompute()
        assert operation.StitchCount == 12
        assert operation.Alignment == "uniform"

        # Public Sewing command creates the M:N network for the sampled curved contour.
        select_edges((sleeve_a, 0), (sleeve_a, 1), (sleeve_a, 2),
                     (sleeve_b, 0), (sleeve_b, 1), (sleeve_b, 2))
        Gui.runCommand("ClothSewing_CreateMNSewing", 0)
        process_events()
        networks = [obj for obj in doc.Objects if getattr(obj, "SewingType", "") == "SewingNetwork"]
        assert len(networks) == 1, "public M:N Sewing command did not create one network"
        network = networks[0]
        assert len(network.Seams) == 3, "curved contour network should contain three seam segments"
        log("mn-network-created relationship=%s seams=%d" % (network.RelationshipId, len(network.Seams)))

        # Create a native simulation scene through the public Simulation command,
        # then select all four pattern pieces through its public task-panel UI.
        activate("ClothSimulationWorkbench", "Cloth Simulation", ["ClothSimulation_CreateDrape", "ClothSimulation_Edit", "ClothSimulation_Step"])
        Gui.runCommand("ClothSimulation_CreateDrape", 0)
        process_events()
        scene = doc.getObject("ClothSimulation")
        assert scene is not None, "public Simulation command did not create a scene"
        scene.ClothPieces = [front, back, sleeve_a, sleeve_b]
        doc.recompute()
        initial_signature = scene.Proxy.source_signature
        initial_particles = int(scene.ParticleCount)
        assert initial_particles > 0
        log("simulation-scene-created particles=%d" % initial_particles)

        Gui.Selection.clearSelection(); Gui.Selection.addSelection(scene); process_events()
        panel = SimulationTaskPanel(scene)
        show_panel(panel, "Simulation")
        panel.iterations.setValue(6)
        # Do not accept the panel here: its selection widgets intentionally
        # edit ClothPieces, and the fixture must retain all four pieces.
        close_panel()
        from SimulationObjects import step_scene
        step_scene(scene, 1)
        doc.recompute()
        assert int(scene.Steps) == 1
        stepped_signature = scene.Proxy.source_signature
        assert stepped_signature == initial_signature, "simulation source changed during a solver-only step"
        assert float(scene.SimulatedTime) > 0.0
        log("simulation-stepped time=%.6f particles=%d" % (float(scene.SimulatedTime), int(scene.ParticleCount)))

        # Persist the full native document, close it, reload it, and verify the
        # sewing graph and simulation source are still connected.
        fd, path = tempfile.mkstemp(prefix="cloth-e2e-", suffix=".FCStd")
        os.close(fd)
        doc.recompute(); doc.saveAs(path)
        operation_name = operation.Name
        network_name = network.Name
        App.closeDocument(doc.Name)
        doc = App.openDocument(path)
        doc.recompute()
        front = doc.getObject("Front")
        back = doc.getObject("Back")
        operation = doc.getObject(operation_name)
        network = doc.getObject(network_name)
        scene = doc.getObject("ClothSimulation")
        assert front is not None and back is not None and operation is not None and network is not None and scene is not None
        assert operation.Seam is not None and operation.PieceA is not None and operation.PieceB is not None
        assert len(network.Seams) == 3
        assert scene.ClothPieces
        log("save-reload-ok operation=%s network=%s pieces=%d" % (operation.Name, network.Name, len(scene.ClothPieces)))

        # Change an upstream pattern parameter. Recompute must rebuild downstream
        # seam-derived geometry and the simulation source signature.
        before_length = float(operation.LengthA)
        before_signature = scene.Proxy.source_signature
        front.Width = 160.0
        doc.recompute()
        after_length = float(operation.LengthA)
        after_signature = scene.Proxy.source_signature
        assert abs(after_length - before_length) > 1e-6, "upstream pattern edit did not change sewing geometry"
        assert after_signature != before_signature, "upstream pattern edit did not invalidate simulation source"
        assert operation.Status == "Length mismatch"
        log("invalidation-ok old_length=%.3f new_length=%.3f" % (before_length, after_length))

        # Re-simulate after the invalidation through the public Simulation task panel.
        Gui.Selection.clearSelection(); Gui.Selection.addSelection(scene); process_events()
        panel = SimulationTaskPanel(scene)
        show_panel(panel, "Simulation after invalidation")
        close_panel()
        from SimulationObjects import reset_scene
        reset_scene(scene)
        step_scene(scene, 2)
        doc.recompute()
        assert int(scene.Steps) == 2
        assert int(scene.ParticleCount) > 0
        assert float(scene.SimulatedTime) > 0.0
        log("resimulation-ok steps=%d particles=%d" % (int(scene.Steps), int(scene.ParticleCount)))
        log("scenario-complete")
    except Exception:
        log("scenario-error")
        log(traceback.format_exc())
        raise
    finally:
        try:
            Gui.Control.closeDialog()
        except Exception:
            pass
        if doc is not None and doc.Name in App.listDocuments():
            App.closeDocument(doc.Name)
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass


if __name__ == "__main__":
    run()
