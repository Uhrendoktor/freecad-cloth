#!/usr/bin/env python3
"""FreeCAD GUI entry point for the workbench benchmark."""
from __future__ import annotations

import runpy

runpy.run_path("tools/benchmark_workbenches.py", run_name="__main__")
