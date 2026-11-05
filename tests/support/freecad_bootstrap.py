# Copyright (C) 2026 FreeCAD Cloth contributors
"""Prepare repository import paths for standalone FreeCAD acceptance scripts."""

from __future__ import annotations

import sys
from pathlib import Path


def prepare_repository_root(script_file: str | Path) -> Path:
    """Return the repository root and remove conflicting root entries from sys.path.

    Args:
        script_file: Path of the standalone FreeCAD acceptance script.

    Returns:
        The repository root inferred from the script location.
    """
    root = Path(script_file).resolve().parents[1]
    sys.path[:] = [entry for entry in sys.path if entry not in ("", str(root))]
    return root
