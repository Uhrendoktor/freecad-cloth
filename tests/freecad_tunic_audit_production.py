"""Run the production tunic audit through its normal, checked-in entry point."""

from __future__ import annotations

import os
import runpy
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT_ENTRY_POINT = ROOT / "tests" / "freecad_tunic_audit.py"


def main() -> None:
    """Delegate to the explicit tunic audit profile without compiling source text."""
    try:
        runpy.run_path(str(AUDIT_ENTRY_POINT), run_name="__main__")
    except BaseException as exc:
        print("production-tunic-audit-wrapper-failed", repr(exc), flush=True)
        print(traceback.format_exc(), flush=True)
        os._exit(1)


if __name__ == "__main__":
    main()
