#!/usr/bin/env python3
"""Run Vulture only on high-confidence dead code in selected core surfaces."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_ROOTS = (
    ROOT / "freecad_cloth" / "common",
    ROOT / "freecad_cloth" / "shared",
    ROOT / "freecad_cloth" / "pattern",
    ROOT / "freecad_cloth" / "sewing",
    ROOT / "freecad_cloth" / "avatar",
    ROOT / "freecad_cloth" / "simulation",
    ROOT / "tools",
)


def allowed(path: Path) -> bool:
    """Return whether a path is in a statically analyzable core surface."""
    try:
        resolved = path.resolve()
        relative = resolved.relative_to(ROOT)
    except ValueError:
        return False
    return any(
        resolved.is_relative_to(root) for root in ALLOWED_ROOTS
    ) and not relative.name.endswith(("Gui.py", "Commands.py", "workbench.py"))


def main() -> int:
    """Run Vulture at 100% confidence for selected files."""
    candidates = [Path(value) for value in sys.argv[1:]]
    if not candidates:
        candidates = [
            path
            for root in ALLOWED_ROOTS
            if root.exists()
            for path in root.rglob("*.py")
        ]
    paths = tuple(str(path) for path in candidates if path.is_file() and allowed(path))
    if not paths:
        return 0
    return subprocess.call([sys.executable, "-m", "vulture", "--min-confidence", "100", *paths])


if __name__ == "__main__":
    raise SystemExit(main())
