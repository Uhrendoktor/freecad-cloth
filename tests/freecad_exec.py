"""Run a FreeCAD Python script and force a real process exit on success/failure.

FreeCAD's GUI launcher can keep the application event loop alive after a script
raises an exception. CI must not turn those failures into timeout-only results.
"""
import os
import runpy
import sys
import traceback
from pathlib import Path


def _write_error(text):
    directory = Path(os.environ.get("CLOTH_E2E_DIR", "/tmp"))
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "freecad-python-error.log").write_text(text, encoding="utf-8")


if len(sys.argv) != 2:
    _write_error("usage: freecad_exec.py TARGET_SCRIPT\n")
    os._exit(2)

target = str(Path(sys.argv[1]).resolve())
try:
    runpy.run_path(target, run_name="__main__")
except BaseException:
    error = traceback.format_exc()
    print(error, file=sys.stderr, flush=True)
    _write_error(error)
    os._exit(1)
else:
    os._exit(0)
