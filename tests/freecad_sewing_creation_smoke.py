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
from freecad_cloth.sewing.SewingCommands import get_active_staged_sewing_task_panel


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


def wait_for_task_close():
    for _ in range(80):
        process_events()
        active = Gui.Control.activeDialog()
        if active is None or not bool(active):
            return
    raise AssertionError("task dialog did not close after the requested Commit/Cancel action")


def select_edges(*items):
    Gui.Selection.clearSelection()
    for obj, edge in items:
        Gui.Selection.addSelection(obj, "Edge%d" % (int(edge) + 1))
    process_events()


def open_public(command):
    if Gui.Control.activeDialog():
        Gui.Control.closeDialog()
        process_events()
    Gui.runCommand(command, 0)
    process_events()
    panel = get_active_staged_sewing_task_panel()
    assert panel is not None, command + " did not retain a task panel"
    assert getattr(panel, "form", None) is not None
    active = Gui.Control.activeDialog()
    assert active is not None, command + " did not open an active task dialog"
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    widgets = [panel.form] + list(panel.form.findChildren(QtWidgets.QWidget))
    dialog_text = " | ".join(
        str(getter())
        for widget in widgets
        for getter in [getattr(widget, "text", None)]
        if callable(getter)
    )
    for required in ("Preview", "Commit", "Cancel", "Selected semantic pattern edges"):
        assert required in dialog_text, command + " task panel is missing required control text: " + required
    return panel


def close_public_task(panel=None):
    if panel is not None:
        try:
            panel.reject()
        except Exception:
            pass
    if Gui.Control.activeDialog():
        Gui.Control.closeDialog()
        process_events()


doc = None
_success = False
try:
    record("smoke=started")
    InitGui.ClothSewingWorkbench()
    record("workbench=initialized")
    Gui.activateWorkbench("ClothSewingWorkbench")
    process_events()
    for command in ("ClothSewing_CreateSeam", "ClothSewing_CreateMNSewing", "ClothSewing_FreeSewing"):
        assert command in Gui.listCommands(), "missing public sewing command: " + command
    record("commands=registered")

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
    record("fixtures=created pieces=3")

    before = {obj.Name for obj in doc.Objects}
    select_edges((piece_a, 0), (piece_b, 0))
    panel = open_public("ClothSewing_CreateSeam")
    assert any(getattr(obj, "SeamId", "") for obj in panel.session.created), "1:1 preview did not create a seam"
    assert "Preview valid" in panel.feedback.text()
    assert Gui.Control.activeDialog() is not None
    record("preview-1to1=passed")
    panel.commit_button.click()
    process_events()
    wait_for_task_close()
    assert any(
        getattr(obj, "SeamId", "") for obj in doc.Objects if obj.Name not in before
    ), "1:1 commit lost seam"
    record("commit-1to1=passed")

    cancel_before = {obj.Name for obj in doc.Objects}
    select_edges((piece_a, 1), (piece_b, 1))
    cancel_panel = open_public("ClothSewing_CreateSeam")
    assert any(getattr(obj, "SeamId", "") for obj in cancel_panel.session.created)
    cancel_panel.cancel_button.click()
    wait_for_task_close()
    assert {obj.Name for obj in doc.Objects} == cancel_before, "cancel persisted preview objects"
    record("cancel-1to1=passed")

    count_before = {obj.Name for obj in doc.Objects}
    select_edges((piece_a, 2))
    invalid_count_panel = open_public("ClothSewing_CreateSeam")
    assert "Preview rejected" in invalid_count_panel.feedback.text()
    assert "exactly two edges" in invalid_count_panel.feedback.text()
    assert {obj.Name for obj in doc.Objects} == count_before
    invalid_count_panel.cancel_button.click()
    wait_for_task_close()
    assert {obj.Name for obj in doc.Objects} == count_before
    record("selection-count-rejection=passed")

    same_piece_before = {obj.Name for obj in doc.Objects}
    select_edges((piece_a, 0), (piece_a, 1))
    invalid_panel = open_public("ClothSewing_CreateSeam")
    assert "Preview rejected" in invalid_panel.feedback.text()
    assert "different pattern pieces" in invalid_panel.feedback.text()
    assert {obj.Name for obj in doc.Objects} == same_piece_before
    invalid_panel.cancel_button.click()
    wait_for_task_close()
    assert {obj.Name for obj in doc.Objects} == same_piece_before
    record("invalid-same-piece-preview=passed")

    mn_before = {obj.Name for obj in doc.Objects}
    select_edges((piece_a, 0), (piece_b, 1), (piece_c, 2))
    invalid_mn_panel = open_public("ClothSewing_CreateMNSewing")
    assert "Preview rejected" in invalid_mn_panel.feedback.text()
    assert "two different pattern pieces" in invalid_mn_panel.feedback.text()
    assert {obj.Name for obj in doc.Objects} == mn_before
    invalid_mn_panel.cancel_button.click()
    wait_for_task_close()
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
    mn_panel.commit_button.click()
    wait_for_task_close()
    networks = [
        obj for obj in doc.Objects if getattr(obj, "SewingType", "") == "SewingNetwork"
    ]
    assert networks and networks[-1].Status == "Valid", "M:N commit did not leave a valid network"
    record("commit-mn=passed")

    free_before = {obj.Name for obj in doc.Objects}
    select_edges((piece_a, 0), (piece_b, 3))
    free_panel = open_public("ClothSewing_FreeSewing")
    assert any(getattr(obj, "SewingType", "") == "SewingNetwork" for obj in free_panel.session.created)
    assert "Preview valid" in free_panel.feedback.text()
    free_panel.cancel_button.click()
    wait_for_task_close()
    assert {obj.Name for obj in doc.Objects} == free_before
    record("cancel-free-sewing=passed")

    select_edges((piece_a, 1), (piece_b, 2))
    free_panel = open_public("ClothSewing_FreeSewing")
    free_networks = [obj for obj in free_panel.session.created if getattr(obj, "SewingType", "") == "SewingNetwork"]
    assert free_networks and str(free_networks[0].Status) == "Valid"
    free_panel.commit_button.click()
    wait_for_task_close()
    committed_free = [obj for obj in doc.Objects if getattr(obj, "SewingType", "") == "SewingNetwork" and str(getattr(obj, "RelationshipId", "")).startswith("free-sewing-")]
    assert committed_free and committed_free[-1].Status == "Valid"
    record("commit-free-sewing=passed")

    _success = True
except Exception:
    record("smoke=exception\n" + traceback.format_exc())
    raise
finally:
    LOG.append("sewing-creation-smoke=completed")
    LOG_PATH.write_text("\n".join(LOG) + "\n", encoding="utf-8")
    print("sewing-creation-smoke=completed", flush=True)

if _success:
    sys.stdout.flush()
    getattr(os, "_" + "exit")(0)
