"""FreeCAD AppRun entrypoint for the garment E2E smoke.

FreeCAD's AppRun script loader does not guarantee the loaded script has
__name__ == "__main__". Execute the import-safe acceptance module through
runpy with an explicit __main__ name so its existing main guard remains the
only acceptance entrypoint.
"""
from pathlib import Path
import runpy

SCRIPT = Path(__file__).with_name("freecad_garment_e2e_smoke.py")
runpy.run_path(str(SCRIPT), run_name="__main__")
