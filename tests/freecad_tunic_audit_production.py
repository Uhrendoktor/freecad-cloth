"""Production tunic audit wrapper using the shared checked-in test implementation."""

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))
main = importlib.import_module("freecad_tunic_audit").main


# FreeCAD's macro runner does not consistently provide the normal CLI __name__
# contract. Dispatch unconditionally, as the checked-in FreeCAD fixtures do.
main()
