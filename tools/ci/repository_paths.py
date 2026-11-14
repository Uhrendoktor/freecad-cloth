# Copyright (C) 2026 FreeCAD Cloth contributors
"""Shared repository-path bootstrap for standalone CI script entrypoints."""

from __future__ import annotations

import sys
from pathlib import Path


def add_repository_root(script_file: str | Path) -> Path:
    """Make a CI script's repository root importable and return that root.

    Args:
        script_file: Filesystem path of the executing CI script.

    Returns:
        Resolved repository root containing the tools and application packages.

    Side Effects:
        Inserts the repository root at the front of sys.path when it is absent.
    """
    repository_root = Path(script_file).resolve().parents[2]
    root_text = str(repository_root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    return repository_root
