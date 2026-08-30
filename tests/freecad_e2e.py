"""Canonical native FreeCAD Pattern -> Sewing -> Simulation acceptance workflow."""
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

ROOT = Path.cwd()
if not (ROOT / "InitGui.py").exists():
    ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
init_gui = ROOT / "InitGui.py"
exec(compile(init_gui.read_text(encoding="utf-8"), str(init_gui), "exec"), globals(), globals())
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
    if Gui.activeWorkbench().name() != name:
        raise AssertionError("expected active workbench %s" % name)
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


def create_native_sketch(piece):
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(piece)
    process_events()
    Gui.runCommand("ClothPattern_CreateSketch", 0)
    process_events()
    sketch = getattr(piece, "Sketch", None)
    if sketch is None or getattr(sketch, "GeometryAuthority", "") != "Sketcher":
        raise AssertionError("PatternPiece did not acquire native Sketcher authority")
    return sketch


def run():
    from PatternGui import PatternDraftingTaskPanel
    from SewingGui import SewingTaskPanel
    from SimulationQualityGui import SimulationQualityTaskPanel
    from freecad_pattern_sketcher_acceptance import exercise_native_sketcher
    doc = App.newDocument("CanonicalClothE2E")
    path = None
    try:
        log("scenario-start")
        front = make_piece(doc, "Front", [(0, 0), (140, 0), (140, 90), (0, 90)], "front")
        back = make_piece(doc, "Back", [(0, 0), (140, 0), (140, 90), (0, 90)], "back")
        back.Placement.Base.x = 170
        import math
        curve = [(80 * math.cos(math.radians(a)), 80 * math.sin(math.radians(a))) for a in (0, 18, 36, 54, 72, 90)]
        sleeve_a = make_piece(doc, "SleeveA", [(0, 0)] + curve, "sleeve-a")
        sleeve_b = make_piece(doc, "SleeveB", [(0, 0)] + curve, "sleeve-b")
        sleeve_b.Placement.Base.x = 210
        doc.recompute()

        activate("ClothPatternWorkbench", "Cloth Pattern", ["ClothPattern_CreatePieceTask", "ClothPattern_EditPiece", "ClothPattern_Show2D", "ClothPattern_AddSeam", "ClothPattern_CreateSketch"])
        front_sketch = create_native_sketch(front)
        back_sketch = create_native_sketch(back)
        sleeve_a_sketch = create_native_sketch(sleeve_a)
        sleeve_b_sketch = create_native_sketch(sleeve_b)
        for sketch in (front_sketch, back_sketch, sleeve_a_sketch, sleeve_b_sketch):
            if getattr(sketch, "GeometryAuthority", "") != "Sketcher":
                raise AssertionError("Sketcher authority was not persisted")
        exercise_native_sketcher(doc, front, front_sketch)
        log("native Sketcher constraints, curved geometry, expression: OK")
        show_panel(PatternDraftingTaskPanel(front), "Pattern Design")
        close_panel()

        select_edges((front, 0), (back, 0))
        Gui.runCommand("ClothPattern_AddSeam", 0); process_events()
        seams = [obj for obj in doc.Objects if getattr(obj, "SeamId", "")]
        assert len(seams) == 1
        main_seam = seams[0]

        activate("ClothSewingWorkbench", "Cloth Sewing", ["ClothSewing_CreateSeam", "ClothSewing_CreateMNSewing", "ClothSewing_CreateOperation", "ClothSewing_EditOperation", "ClothSewing_Validate"])
        Gui.Selection.clearSelection(); Gui.Selection.addSelection(main_seam); process_events()
        Gui.runCommand("ClothSewing_CreateOperation", 0); process_events()
        operations = [obj for obj in doc.Objects if getattr(obj, "SewingType", "") == "SewingOperation"]
        assert len(operations) == 1 and operations[0].Status == "Valid"
        operation = operations[0]
        Gui.Selection.clearSelection(); Gui.Selection.addSelection(operation); process_events()
        panel = SewingTaskPanel(operation); show_panel(panel, "Sewing")
        panel.stitches.setValue(12); panel.alignment.setCurrentText("uniform")
        assert panel.accept() is True; close_panel(); doc.recompute()
        assert operation.StitchCount == 12 and operation.Alignment == "uniform"
        select_edges((sleeve_a, 0), (sleeve_a, 1), (sleeve_a, 2), (sleeve_b, 0), (sleeve_b, 1), (sleeve_b, 2))
        Gui.runCommand("ClothSewing_CreateMNSewing", 0); process_events()
        networks = [obj for obj in doc.Objects if getattr(obj, "SewingType", "") == "SewingNetwork"]
        assert len(networks) == 1 and len(networks[0].Seams) == 3
        network = networks[0]

        activate("ClothSimulationWorkbench", "Cloth Simulation", ["ClothSimulation_Create", "ClothSimulation_Edit", "ClothSimulation_Step"])
        Gui.runCommand("ClothSimulation_Create", 0); process_events()
        scene = doc.getObject("ClothSimulation")
        assert scene is not None
        scene.ClothPieces = [front, back, sleeve_a, sleeve_b]
        scene.QualityPreset = "Fast"
        scene.Steps = 4
        doc.recompute()
        assert int(scene.ParticleCount) > 0 and scene.FiniteState
        working_particles = int(scene.ParticleCount)
        initial_signature = scene.Proxy.source_signature
        Gui.Selection.clearSelection(); Gui.Selection.addSelection(scene); process_events()
        show_panel(SimulationQualityTaskPanel(scene), "Simulation Quality"); close_panel()
        scene.QualityPreset = "Final"
        scene.Steps = 1
        doc.recompute()
        final_particles = int(scene.ParticleCount)
        assert final_particles > working_particles
        assert scene.Proxy.source_signature == initial_signature

        fd, path = tempfile.mkstemp(prefix="cloth-e2e-", suffix=".FCStd"); os.close(fd)
        doc.recompute(); doc.saveAs(path)
        operation_name = operation.Name; network_name = network.Name
        App.closeDocument(doc.Name)
        doc = App.openDocument(path); doc.recompute()
        front = doc.getObject("Front"); operation = doc.getObject(operation_name); network = doc.getObject(network_name); scene = doc.getObject("ClothSimulation")
        assert front is not None and operation is not None and network is not None and scene is not None
        assert getattr(front, "GeometryAuthority", "") == "Sketcher"
        assert operation.Seam is not None and operation.PieceA is not None and operation.PieceB is not None
        assert len(network.Seams) == 3 and scene.ClothPieces
        reloaded_sketch = front.Sketch
        assert reloaded_sketch.getExpression("Constraints.PatternWidth") == "42 mm"
        assert any(c.Type == "Tangent" for c in reloaded_sketch.Constraints)
        assert any(c.Type == "Symmetric" for c in reloaded_sketch.Constraints)

        before_length = float(operation.LengthA); before_signature = scene.Proxy.source_signature
        front.Width = 160.0; doc.recompute()
        after_length = float(operation.LengthA); after_signature = scene.Proxy.source_signature
        assert abs(after_length - before_length) > 1e-6
        assert after_signature != before_signature and operation.Status == "Length mismatch"
        Gui.Selection.clearSelection(); Gui.Selection.addSelection(scene); process_events()
        show_panel(SimulationQualityTaskPanel(scene), "Simulation after invalidation"); close_panel()
        scene.QualityPreset = "Balanced"
        scene.Steps = 2
        doc.recompute()
        assert int(scene.ParticleCount) > 0 and scene.FiniteState
        log("three PatternPieces plus sleeves: OK")
        log("native Sketcher authority: OK")
        log("persisted seam and M:N sewing network: OK")
        log("quality density %s -> %s: OK" % (working_particles, final_particles))
        log("save/reload and upstream edit invalidation: OK")
        log("re-simulation after invalidation: OK")
        log("scenario-complete")
    except Exception:
        log("scenario-error"); log(traceback.format_exc()); raise
    finally:
        try: Gui.Control.closeDialog()
        except Exception: pass
        if doc is not None and doc.Name in App.listDocuments(): App.closeDocument(doc.Name)
        if path:
            try: os.unlink(path)
            except OSError: pass
        try:
            window = Gui.getMainWindow()
            if window is not None: window.close()
        except Exception: pass


if __name__ == "__main__":
    run()
