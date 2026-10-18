# Copyright (C) 2026 FreeCAD Cloth contributors
"""Production tunic visual/simulation audit entry point.

The shared FreeCAD screenshot fixture owns all executable behavior. This module
selects its explicit production audit profile and runs the checked-in fixture
without generating or modifying Python source.
"""

import ast
import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests" / "freecad_screenshot_source.py"


def main() -> int:
    """Run the checked-in screenshot fixture with production tunic acceptance.

    Returns:
        Zero after the fixture passes or after a requested syntax-only check succeeds.
    """
    os.environ["CLOTH_PBD_COLLISION_MODE"] = "mesh"
    os.environ["CLOTH_TUNIC_AUDIT_PROFILE"] = "production"
    os.environ["CLOTH_TUNIC_AUDIT_SKIP_CANONICAL_ACCEPTANCE"] = "1"
    if "--syntax-check" in sys.argv:
        ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
        print("tunic-audit-source-syntax=passed", flush=True)
        return 0
    runpy.run_path(str(SOURCE), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
