"""Run the production tunic audit through its normal, checked-in entry point."""

from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT_ENTRY_POINT = ROOT / "tests" / "freecad_tunic_audit.py"


def main() -> None:
    """Delegate to the explicit tunic audit profile without compiling source text."""
    runpy.run_path(str(AUDIT_ENTRY_POINT), run_name="__main__")


if __name__ == "__main__":
    main()
