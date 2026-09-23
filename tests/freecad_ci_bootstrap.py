"""Bootstrap a FreeCAD CI script without exposing the repository during FreeCAD startup."""
import os
import runpy
import sys


ROOT = "/workspace"
script = os.environ["CLOTH_CI_SCRIPT"]

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

runpy.run_path(script, run_name="__main__")
