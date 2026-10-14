"""Run the canonical screenshot fixture with the explicit production tunic profile."""

from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "tests" / "freecad_screenshot_source.py"


def main() -> None:
    """Select the production tunic scenario and run the checked-in fixture directly."""
    if "--syntax-check" in sys.argv:
        compile(SOURCE_PATH.read_text(encoding="utf-8"), str(SOURCE_PATH), "exec")
        print("tunic-audit-source-syntax=passed", flush=True)
        return

    os.environ["CLOTH_PBD_COLLISION_MODE"] = "mesh"
    os.environ["CLOTH_TUNIC_AUDIT_PROFILE"] = "production"
    os.environ["CLOTH_TUNIC_AUDIT_SKIP_CANONICAL_ACCEPTANCE"] = "1"
    os.environ["CLOTH_TUNIC_AUDIT_RUN_AVATAR_ACCEPTANCE"] = "1"
    runpy.run_path(str(SOURCE_PATH), run_name="__main__")


if __name__ == "__main__":
    main()
