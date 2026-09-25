"""Minimal FreeCAD 1.1.0 task-dialog teardown probe.

The file is intentionally runnable by FreeCAD as a startup script. It compares:
1. Gui.Control.closeDialog() invoked synchronously while the script is still
   executing during FreeCAD startup/delayedStartup.
2. The same close operation invoked from a QTimer callback after the startup
   script returns and the normal Qt event loop is running.

This is research instrumentation only; it does not assert a preferred outcome.
"""
from __future__ import annotations

import os
import time

import FreeCAD as App
import FreeCADGui as Gui

try:
    from PySide import QtCore, QtWidgets
except ImportError:
    from PySide2 import QtCore, QtWidgets


MODE = os.environ.get("CLOTH_TASK_DIALOG_PROBE_MODE", "sync").strip().lower()
LOG_PATH = os.environ.get(
    "CLOTH_TASK_DIALOG_PROBE_LOG",
    "/workspace/artifacts/task-dialog-loop-probe.log",
)
LOG = []


def record(message: str) -> None:
    line = f"task-dialog-probe={message}"
    LOG.append(line)
    print(line, flush=True)
    path = os.path.abspath(LOG_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")
        handle.flush()


def dialog_state() -> str:
    try:
        dialog = Gui.Control.activeDialog()
    except Exception as exc:
        return f"error:{type(exc).__name__}"
    if dialog is None:
        return "none"
    try:
        truth = bool(dialog)
    except Exception:
        truth = "error"
    try:
        visible = bool(dialog.isVisible())
    except Exception:
        visible = "na"
    return f"{type(dialog).__name__}:bool={truth}:visible={visible}"


class ProbeTaskPanel:
    def __init__(self) -> None:
        self.form = QtWidgets.QWidget()
        self.form.setObjectName("ClothTaskDialogLoopProbe")
        layout = QtWidgets.QVBoxLayout(self.form)
        layout.addWidget(QtWidgets.QLabel("FreeCAD task-dialog loop probe"))

    def getStandardButtons(self) -> int:
        return 0


doc = App.newDocument("TaskDialogLoopProbe")
panel = ProbeTaskPanel()
Gui.Control.showDialog(panel)
if not panel.form.isVisible():
    panel.form.show()
record(f"mode={MODE}")
record(f"before-close activeDialog={dialog_state()}")

app = QtWidgets.QApplication.instance()
if app is None:
    raise RuntimeError("Qt application instance is unavailable")


def finish(label: str) -> None:
    record(f"{label} activeDialog={dialog_state()}")
    try:
        App.closeDocument(doc.Name)
    except Exception:
        pass
    app.quit()


if MODE == "sync":
    Gui.Control.closeDialog()
    record(f"after-sync-close-immediate activeDialog={dialog_state()}")
    QtCore.QTimer.singleShot(0, lambda: finish("after-sync-close-event-loop"))
elif MODE == "deferred":
    def deferred_close() -> None:
        record(f"deferred-callback-enter activeDialog={dialog_state()}")
        Gui.Control.closeDialog()
        record(f"after-deferred-close-immediate activeDialog={dialog_state()}")
        QtCore.QTimer.singleShot(
            0, lambda: finish("after-deferred-close-event-loop")
        )

    QtCore.QTimer.singleShot(0, deferred_close)
else:
    raise RuntimeError(f"unsupported CLOTH_TASK_DIALOG_PROBE_MODE={MODE!r}")

record("startup-script-returning")
