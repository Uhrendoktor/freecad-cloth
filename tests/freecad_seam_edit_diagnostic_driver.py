#!/usr/bin/env python3
"""Exact-image three-path diagnostic for native seam-side Sketcher edit."""
from __future__ import annotations

import argparse
import os
import signal
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

DIAG_HELPER = r'''
def _diag_mark(label):
    print("diag-marker=%s t=%.6f" % (label, time.monotonic()), flush=True)

def _diag_state(label):
    doc = App.ActiveDocument
    gui_doc = Gui.activeDocument()
    try:
        in_edit = bool(gui_doc.getInEdit()) if gui_doc is not None else None
    except Exception as exc:
        in_edit = "error:%s" % type(exc).__name__
    try:
        dialog = Gui.Control.activeDialog()
    except Exception as exc:
        dialog = "error:%s" % type(exc).__name__
    if dialog is None:
        dialog_desc = "none"
    else:
        try:
            dialog_desc = "%s visible=%s objectName=%s" % (
                type(dialog).__name__,
                bool(dialog.isVisible()) if hasattr(dialog, "isVisible") else "na",
                str(dialog.objectName()) if hasattr(dialog, "objectName") else "na",
            )
        except Exception as exc:
            dialog_desc = "error:%s" % type(exc).__name__
    selected = []
    try:
        for item in Gui.Selection.getSelectionEx():
            selected.append(
                "%s:%s" % (
                    getattr(item.Object, "Name", "?"),
                    ",".join(item.SubElementNames),
                )
            )
    except Exception as exc:
        selected = ["error:%s" % type(exc).__name__]
    pending_tx = tx_empty = None
    if doc is not None:
        fn = getattr(doc, "hasPendingTransaction", None)
        if callable(fn):
            try:
                pending_tx = bool(fn())
            except Exception as exc:
                pending_tx = "error:%s" % type(exc).__name__
        fn = getattr(doc, "isTransactionEmpty", None)
        if callable(fn):
            try:
                tx_empty = bool(fn())
            except Exception as exc:
                tx_empty = "error:%s" % type(exc).__name__
    pending_cmd = None
    command_cls = getattr(Gui, "Command", None)
    pending_fn = getattr(command_cls, "hasPendingCommand", None) if command_cls else None
    if callable(pending_fn):
        try:
            pending_cmd = bool(pending_fn())
        except Exception as exc:
            pending_cmd = "error:%s" % type(exc).__name__
    _diag_mark(
        "state label=%s in_edit=%s activeDialog=%s pendingTx=%s txEmpty=%s "
        "pendingCommand=%s selection=%s"
        % (
            label,
            in_edit,
            dialog_desc,
            pending_tx,
            tx_empty,
            pending_cmd,
            "|".join(selected),
        )
    )
'''

PREFIX = """import time
import FreeCAD as App
import FreeCADGui as Gui
try:
    from PySide import QtCore, QtWidgets
except ImportError:
    from PySide2 import QtCore, QtWidgets
""" + DIAG_HELPER + "\n"

AUTORUN = """\ntry:
    run_acceptance()
except BaseException:
    _quit_application()
    raise
"""

SEAM_COMMAND = '        Gui.runCommand("ClothSewing_EditSeamSideA", 0)'


def instrument_handler(sewing_source: str) -> str:
    start = sewing_source.index("def _edit_selected_seam_side(side):")
    end = sewing_source.index("\ndef edit_selected_seam_side_a", start)
    handler = sewing_source[start:end]
    replacements = [
        (
            "    focus_selected_seam_3d()",
            "    _diag_mark('before-focus')\n"
            "    _diag_state('before-focus')\n"
            "    focus_selected_seam_3d()\n"
            "    _diag_mark('after-focus')\n"
            "    _diag_state('after-focus')",
        ),
        (
            "    if Gui.activeDocument().getInEdit():\n"
            "        Gui.activeDocument().resetEdit()",
            "    if Gui.activeDocument().getInEdit():\n"
            "        _diag_mark('before-reset-edit')\n"
            "        _diag_state('before-reset-edit')\n"
            "        Gui.activeDocument().resetEdit()\n"
            "        _diag_mark('after-reset-edit')\n"
            "        _diag_state('after-reset-edit')",
        ),
        (
            "    Gui.Selection.clearSelection()\n"
            "    Gui.Selection.addSelection(piece)\n"
            "    Gui.activeDocument().setEdit(sketch.Name)",
            "    _diag_mark('before-patternpiece-selection')\n"
            "    Gui.Selection.clearSelection()\n"
            "    _diag_mark('after-clear-selection-before-patternpiece')\n"
            "    Gui.Selection.addSelection(piece)\n"
            "    _diag_mark('after-patternpiece-selection')\n"
            "    _diag_state('before-set-edit')\n"
            "    _diag_mark('before-set-edit-events')\n"
            "    QtWidgets.QApplication.processEvents()\n"
            "    _diag_mark('after-pre-set-edit-events')\n"
            "    QtCore.QTimer.singleShot(100, lambda: _diag_mark('timer-during-set-edit'))\n"
            "    _diag_mark('before-set-edit')\n"
            "    Gui.activeDocument().setEdit(sketch.Name)\n"
            "    _diag_mark('after-set-edit')\n"
            "    _diag_state('after-set-edit')\n"
            "    QtWidgets.QApplication.processEvents()\n"
            "    _diag_mark('after-set-edit-events')",
        ),
        (
            '    Gui.Selection.clearSelection()\n'
            '    Gui.Selection.addSelection(sketch, "Edge%d" % (edge_index + 1))',
            '    _diag_mark("before-edge-selection")\n'
            '    Gui.Selection.clearSelection()\n'
            '    _diag_mark("after-edge-clear-selection")\n'
            '    Gui.Selection.addSelection(sketch, "Edge%d" % (edge_index + 1))\n'
            '    _diag_mark("after-edge-selection")\n'
            '    _diag_state("after-edge-selection")',
        ),
    ]
    for old, new in replacements:
        if handler.count(old) != 1:
            raise RuntimeError("instrumentation transform count != 1")
        handler = handler.replace(old, new, 1)
    return "from freecad_cloth.sewing.SewingCommands import *\n" + handler + "\n"


def make_case(acceptance: str, sewing: str, case: str) -> str:
    if acceptance.count(SEAM_COMMAND) != 1:
        raise RuntimeError("acceptance seam command count != 1")
    if AUTORUN not in acceptance:
        raise RuntimeError("acceptance autorun block changed unexpectedly")

    source = PREFIX + acceptance.replace(AUTORUN, "\n", 1)
    if case == "command":
        replacement = """        _diag_mark("before-command")
        _diag_state("before-command")
        Gui.runCommand("ClothSewing_EditSeamSideA", 0)
        _diag_mark("after-command")
        _diag_state("after-command")
        return"""
    elif case == "direct":
        replacement = """        _diag_mark("before-direct-handler")
        _diag_state("before-direct-handler")
        from freecad_cloth.sewing.SewingCommands import edit_selected_seam_side_a
        edit_selected_seam_side_a()
        _diag_mark("after-direct-handler")
        _diag_state("after-direct-handler")
        return"""
    elif case == "instrumented":
        source = PREFIX + instrument_handler(sewing) + acceptance.replace(AUTORUN, "\n", 1)
        replacement = """        _diag_mark("before-instrumented-handler")
        _diag_state("before-instrumented-handler")
        _edit_selected_seam_side("A")
        _diag_mark("after-instrumented-handler")
        _diag_state("after-instrumented-handler")
        return"""
    else:
        raise ValueError(case)
    return source.replace(SEAM_COMMAND, replacement, 1)


def run_case(case: str, source: str, target: Path, out_dir: Path) -> int:
    case_dir = Path(tempfile.mkdtemp(prefix=f"seam-diag-{case}-", dir="/tmp"))
    case_file = case_dir / f"{case}.py"
    case_file.write_text(source, encoding="utf-8")
    home = case_dir / "home"
    data = case_dir / "data"
    temp = case_dir / "temp"
    runtime = case_dir / "runtime"
    for item in (home, data, temp, runtime):
        item.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env.update({
        "FREECAD_USER_HOME": str(home),
        "FREECAD_USER_DATA": str(data),
        "FREECAD_USER_TEMP": str(temp),
        "XDG_RUNTIME_DIR": str(runtime),
        "PYTHONUNBUFFERED": "1",
    })

    log = out_dir / f"{case}.log"
    started = time.monotonic()
    with log.open("w", encoding="utf-8") as handle:
        proc = subprocess.Popen(
            ["setsid", "/opt/freecad/AppRun", str(case_file)],
            cwd=str(target),
            env=env,
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        watchdog = subprocess.Popen(
            ["bash", "-lc", f"sleep 8; kill -KILL -- -{proc.pid}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        try:
            rc = proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            rc = 124
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass
        finally:
            try:
                watchdog.kill()
            except ProcessLookupError:
                pass

    elapsed = time.monotonic() - started
    with (out_dir / "summary.log").open("a", encoding="utf-8") as handle:
        handle.write(f"case={case} exit={rc} elapsed={elapsed:.3f}s\n")
    shutil.rmtree(case_dir, ignore_errors=True)
    return int(rc)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    acceptance = (args.root / "tests/freecad_sketcher_acceptance.py").read_text(encoding="utf-8")
    sewing = (args.root / "freecad_cloth/sewing/SewingCommands.py").read_text(encoding="utf-8")

    results = {}
    for case in ("command", "direct", "instrumented"):
        results[case] = run_case(case, make_case(acceptance, sewing, case), args.root, args.out)

    (args.out / "result.txt").write_text(
        "\n".join(f"{name}={code}" for name, code in results.items()) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
