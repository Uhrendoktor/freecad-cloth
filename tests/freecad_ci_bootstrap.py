"""Bootstrap a FreeCAD GUI acceptance script from a neutral startup directory."""
import os
import runpy
import sys


ROOT = "/workspace"
script = os.environ["CLOTH_CI_SCRIPT"]

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

runpy.run_path(script, run_name="__main__")
