#!/usr/bin/env python3
"""FreeCAD GUI entry point for the workbench benchmark."""
from __future__ import annotations

import pathlib
import runpy
import sys

# FreeCAD's GUI launcher does not reliably retain the checkout directory on
# sys.path. Add the repository root explicitly before loading the benchmark.
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
runpy.run_path(str(ROOT / "tools" / "benchmark_workbenches.py"), run_name="__main__")
