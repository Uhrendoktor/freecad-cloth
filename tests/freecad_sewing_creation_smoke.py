"""Real-FreeCAD smoke coverage for public staged sewing Preview/Commit/Cancel."""
from pathlib import Path
import os
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import FreeCAD as App
import FreeCADGui as Gui
import InitGui

from freecad_cloth.pattern.PatternModel import PatternPiece
from freecad_cloth.pattern.PatternObjects import add_pattern_piece


LOG_PATH = Path(os.environ.get("CLOTH_SEWING_SMOKE_LOG", ROOT / "artifacts" / "sewing-creation-smoke.log"))
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
LOG = []
LOG_PATH.write_text("", encoding="utf-8")


def process_events():
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    QtWidgets.QApplication.processEvents()
    Gui.updateGui()
    QtWidgets.QApplication.processEvents()


def record(message):
    LOG.append(message)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(message + "\n")
        handle.flush()
    print(message, flush=True)


def select_edges(*items):
    Gui.Selection.clearSelection()
    for obj, edge in items:
        Gui.Selection.addSelection(obj, "Edge%d" % (int(edge) + 1))
    process_events()


def open_public(command):
    record("open-public=%s=begin" % command)
    if Gui.Control.activeDialog():
        Gui.Control.closeDialog()
        process_events()
    try:
        Gui.runCommand(command, 0)
        process_events()
        panel = Gui.Control.activeDialog()
        assert panel is not None, command + " did not open a task panel"
        assert getattr(panel, "form", None) is not None
        record("open-public=%s=passed" % command)
        return panel
    except BaseException as exc:
        record("open-public=%s=failed %r" % (command, exc))
        record(traceback.format_exc())
        raise


def close_public_task():
    if Gui.Control.activeDialog():
        Gui.Control.closeDialog()
        process_events()


record("startup=begin")
try:
    record("initgui=begin")
    workbench = InitGui.ClothSewingWorkbench()
    record("initgui=passed")
    record("activate-workbench=begin")
    Gui.activateWorkbench("ClothSewingWorkbench")
    process_events()
    record("activate-workbench=passed")
    record("commands=%s" % ",".join(sorted(name for name in ("ClothSewing_CreateSeam", "ClothSewing_CreateMNSewing") if name in Gui.listCommands())))
    for command in ("ClothSewing_CreateSeam", "ClothSewing_CreateMNSewing"):
        assert command in Gui.listCommands(), "missing public sewing command: " + command
    record("command-contract=passed")
except BaseException as exc:
    record("startup-stage=failed %r" % (exc,))
    record(traceback.format_exc())
    raise

doc = App.newDocument("SewingCreationSmoke")
piece_a = add_pattern_piece(
    doc,
    PatternPiece("SmokeA", [(0, 0), (100, 0), (100, 100), (0, 100)], id="smoke-a"),
)
piece_b = add_pattern_piece(
    doc,
    PatternPiece("SmokeB", [(0, 0), (100, 0), (100, 100), (0, 100)], id="smoke-b"),
)
piece_c = add_pattern_piece(
    doc,
    PatternPiece("SmokeC", [(0, 0), (100, 0), (100, 100), (0, 100)], id="smoke-c"),
)
doc.recompute()

try:
    before = {obj.Name for obj in doc.Objects}
    select_edges((piece_a, 0), (piece_b, 0))
    panel = open_public("ClothSewing_CreateSeam")
    assert any(getattr(obj, "SeamId", "") for obj in panel.session.created), "1:1 preview did not create a seam"
    assert "Preview valid" in panel.feedback.text()
    assert Gui.Control.activeDialog() is panel
    record("preview-1to1=passed")
    panel.accept()
    process_events()
    assert Gui.Control.activeDialog() is None
    assert any(
        getattr(obj, "SeamId", "") for obj in doc.Objects if obj.Name not in before
    ), "1:1 commit lost seam"
    record("commit-1to1=passed")

    cancel_before = {obj.Name for obj in doc.Objects}
    select_edges((piece_a, 1), (piece_b, 1))
    cancel_panel = open_public("ClothSewing_CreateSeam")
    assert any(getattr(obj, "SeamId", "") for obj in cancel_panel.session.created)
    cancel_panel.reject()
    process_events()
    assert Gui.Control.activeDialog() is None
    assert {obj.Name for obj in doc.Objects} == cancel_before, "cancel persisted preview objects"
    record("cancel-1to1=passed")

    count_before = {obj.Name for obj in doc.Objects}
    select_edges((piece_a, 2))
    invalid_count_panel = open_public("ClothSewing_CreateSeam")
    assert "Preview rejected" in invalid_count_panel.feedback.text()
    assert "exactly two edges" in invalid_count_panel.feedback.text()
    assert {obj.Name for obj in doc.Objects} == count_before
    invalid_count_panel.reject()
    process_events()
    assert Gui.Control.activeDialog() is None
    assert {obj.Name for obj in doc.Objects} == count_before
    record("selection-count-rejection=passed")

    same_piece_before = {obj.Name for obj in doc.Objects}
    select_edges((piece_a, 0), (piece_a, 1))
    invalid_panel = open_public("ClothSewing_CreateSeam")
    assert "Preview rejected" in invalid_panel.feedback.text()
    assert "different pattern pieces" in invalid_panel.feedback.text()
    assert {obj.Name for obj in doc.Objects} == same_piece_before
    invalid_panel.reject()
    process_events()
    assert Gui.Control.activeDialog() is None
    assert {obj.Name for obj in doc.Objects} == same_piece_before
    record("invalid-same-piece-preview=passed")

    mn_before = {obj.Name for obj in doc.Objects}
    select_edges((piece_a, 0), (piece_b, 1), (piece_c, 2))
    invalid_mn_panel = open_public("ClothSewing_CreateMNSewing")
    assert "Preview rejected" in invalid_mn_panel.feedback.text()
    assert "two different pattern pieces" in invalid_mn_panel.feedback.text()
    assert {obj.Name for obj in doc.Objects} == mn_before
    invalid_mn_panel.reject()
    process_events()
    assert Gui.Control.activeDialog() is None
    assert {obj.Name for obj in doc.Objects} == mn_before
    record("invalid-mn-partition-preview=passed")

    select_edges((piece_a, 0), (piece_a, 1), (piece_b, 0), (piece_b, 1))
    mn_panel = open_public("ClothSewing_CreateMNSewing")
    assert any(
        getattr(obj, "SewingType", "") == "SewingNetwork"
        for obj in mn_panel.session.created
    )
    assert "Preview valid" in mn_panel.feedback.text()
    record("preview-mn=passed")
    mn_panel.accept()
    process_events()
    assert Gui.Control.activeDialog() is None
    networks = [
        obj for obj in doc.Objects if getattr(obj, "SewingType", "") == "SewingNetwork"
    ]
    assert networks and networks[-1].Status == "Valid", "M:N commit did not leave a valid network"
    record("commit-mn=passed")
finally:
    try:
        close_public_task()
        Gui.Selection.clearSelection()
        if App.ActiveDocument is not None and App.ActiveDocument.Name == doc.Name:
            App.closeDocument(doc.Name)
        process_events()
    finally:
        LOG_PATH.write_text("\n".join(LOG) + "\n", encoding="utf-8")
        print("sewing-creation-smoke=completed", flush=True)
